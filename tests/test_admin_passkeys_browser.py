"""真实 HTTPS 来源的虚拟认证器回归；全部请求留在隔离 WSGI 与临时库。"""

from datetime import timedelta, timezone
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

import pytest
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.test import Client
from werkzeug.wrappers import Response

from tests.browser_support import BrowserSession, ROOT
from tests.test_admin_auth import otp, query
from tests.test_admin_browser import browser_gate, button, expect


pytestmark = [pytest.mark.auth_database, pytest.mark.browser]
BASE = "/api/admin/auth/passkeys"
BUSY = re.compile(r"(?:^|\s)ant-btn-loading(?:\s|$)")
CANCELLED = "通行密钥确认已取消、超时或设备上暂无此站点的密钥。"


class PasskeyBrowser(BrowserSession):
    def __init__(self, page, app, account, origin, evidence, requests):
        super().__init__(page, app, account)
        self.origin, self.evidence, self.requests = origin, evidence, requests

    def login(self):
        page = self.page
        page.clock.set_fixed_time(self.app.test_clock[0].replace(tzinfo=timezone.utc))
        page.goto(self.origin + "/login", wait_until="networkidle")
        page.get_by_label("账号", exact=True).fill(self._account["username"])
        page.get_by_label("密码", exact=True).fill(self._account["password"])
        page.get_by_label("Authenticator 验证码", exact=True).fill(otp(self.app, self._account))
        button(page, "使用密码和动态码登录")
        expect(page.get_by_role("button", name="退出登录", exact=True)).to_be_visible()

    def keys(self):
        self.navigate("系统管理")
        self.page.get_by_role("tab", name="通行密钥", exact=True).click()
        expect(self.page.get_by_role("button", name="登记通行密钥", exact=True)).to_be_visible()

    def posts(self, suffix):
        return sum(method == "POST" and path == BASE + suffix for method, path, _ in self.requests)

    def capture(self, name, width=1920, height=1080):
        self.page.set_viewport_size({"width": width, "height": height})
        self.page.screenshot(
            path=str(self.evidence / name), full_page=True, animations="disabled",
            mask=[self.page.locator('input[type="password"], #code, [data-private]')],
        )


@pytest.fixture
def passkey_browser(request, auth_app, admin_account):
    from playwright.sync_api import sync_playwright

    slot, origin = getattr(request, "param", ("production", "https://admin.bumbum.cc"))
    auth_app.config.update(APP_ENV="production", HANGZHOU_SLOT=slot,
                           ADMIN_ORIGIN=origin, TEST_ADMIN_PASSKEYS=False)
    dist = ROOT / "frontend/admin/dist"
    if not (dist / "index.html").is_file():
        pytest.fail("请先构建正式后台；HTTPS 通行密钥回归不会使用替代页面。")

    def fallback(environ, start_response):
        if environ.get("PATH_INFO") in {"/", "/login", "/overview", "/system"}:
            return Response((dist / "index.html").read_bytes(), mimetype="text/html")(environ, start_response)
        return auth_app(environ, start_response)

    backend = Client(SharedDataMiddleware(fallback, {"/": str(dist)}, cache=False),
                     Response, use_cookies=False)
    requests, blocked, errors = [], [], []

    def local_request(route):
        incoming = route.request
        parts = urlsplit(incoming.url)
        if f"{parts.scheme}://{parts.netloc}" != origin:
            blocked.append(parts.netloc)
            route.abort("blockedbyclient")
            return
        path = parts.path + ("?" + parts.query if parts.query else "")
        response = backend.open(path, base_url=origin, method=incoming.method,
                                headers=incoming.all_headers(), data=incoming.post_data_buffer)
        requests.append((incoming.method, parts.path, response.status_code))
        headers = {key: value for key, value in response.headers
                   if key.lower() not in {"content-length", "content-encoding", "transfer-encoding"}}
        route.fulfill(status=response.status_code, headers=headers, body=response.get_data())

    artifacts = Path(request.config.getoption("--browser-artifacts"))
    if artifacts.is_symlink():
        raise ValueError("截图目录不可为符号链接")
    artifacts.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix=f"passkeys-{slot}-", dir=artifacts))
    with sync_playwright() as playwright:
        options = {"headless": True, "args": ["--host-resolver-rules=MAP * 127.0.0.1"]}
        executable = request.config.getoption("--browser-executable")
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, service_workers="block")
        # 必须在创建页面和首次导航前接管；不允许任何请求落到真实测试或生产站点。
        context.route("**/*", local_request)
        context.route_web_socket("**/*", lambda websocket: websocket.close())
        page = context.new_page()
        page.set_default_timeout(12000)
        page.on("pageerror", lambda error: errors.append(type(error).__name__))
        cdp = context.new_cdp_session(page)
        cdp.send("WebAuthn.enable")
        authenticator = cdp.send("WebAuthn.addVirtualAuthenticator", {"options": {
            "protocol": "ctap2", "transport": "internal", "hasResidentKey": True,
            "hasUserVerification": True, "isUserVerified": True,
            "automaticPresenceSimulation": True,
        }})["authenticatorId"]
        session = PasskeyBrowser(page, auth_app, admin_account, origin, evidence, requests)
        try:
            yield session
            assert not blocked, "浏览器尝试请求当前隔离来源以外的地址；请求已阻断。"
            assert not errors, "浏览器发生未捕获错误；仅记录错误类型。"
        finally:
            try:
                if getattr(getattr(request.node, "report_call", None), "failed", False):
                    session.capture("failure.png")
            except Exception:
                pass
            try:
                cdp.send("WebAuthn.removeVirtualAuthenticator", {"authenticatorId": authenticator})
            finally:
                try:
                    context.close()
                finally:
                    browser.close()


def register(browser):
    button(browser.page, "登记通行密钥")
    expect(browser.page.get_by_role("button", name="登记通行密钥", exact=True)).not_to_have_class(BUSY)
    expect(browser.page.get_by_role("button", name="撤销", exact=True)).to_have_count(1)
    assert browser.posts("/register/finish") == 1


def audit_from_ui(browser, action, label):
    page = browser.page
    browser.navigate("系统管理")
    page.get_by_role("tab", name="操作审计", exact=True).click()
    page.get_by_label("对象或结果关键词", exact=True).fill(str(browser._account["id"]))
    operation = page.get_by_label("操作筛选", exact=True)
    operation.fill(label)
    page.locator(".ant-select-dropdown:visible .ant-select-item-option").filter(has_text=label).click()
    button(page, "查询")
    expect(page).to_have_url(re.compile(r"action=" + re.escape(action)))
    row = page.locator("tbody tr.ant-table-row")
    expect(row).to_have_count(1)
    expect(row).to_contain_text(label)
    expect(row).to_contain_text(browser._account["username"])
    row.get_by_role("button", name=re.compile("查看详情")).click()
    details = page.get_by_role("dialog", name="操作日志详情", exact=True)
    expect(details).to_contain_text(label)
    expect(details).to_contain_text("已完成")
    details.get_by_role("button", name="关闭", exact=True).click()
    details.wait_for(state="hidden")


@pytest.mark.parametrize("passkey_browser", [
    ("production", "https://admin.bumbum.cc"),
    ("test", "https://test.bumbum.cc"),
], indirect=True, ids=["production", "test"])
def test_https_passkey_lifecycle_and_password_recovery(passkey_browser):
    browser = passkey_browser
    page, app = browser.page, browser.app
    browser.login()
    assert page.evaluate("window.isSecureContext && window.location.origin") == browser.origin
    browser.keys()
    expect(page.get_by_text("暂无通行密钥", exact=True)).to_be_visible()
    register(browser)
    key_id = query(app, "SELECT id FROM admin_passkey")[0]["id"]
    assert [r["action"] for r in query(app, "SELECT action FROM admin_audit ORDER BY id")] == ["auth.passkey.register"]
    browser.capture("01-registered-1920.png")

    button(page, "退出登录")
    expect(page.get_by_role("heading", name="管理员登录", exact=True)).to_be_visible()
    button(page, "使用通行密钥登录")
    expect(page.get_by_role("button", name="退出登录", exact=True)).to_be_visible()
    assert browser.posts("/login/finish") == 1
    assert query(app, "SELECT last_used_at FROM admin_passkey")[0]["last_used_at"] is not None
    browser.keys()
    browser.capture("02-passkey-login-1280.png", 1280, 720)

    button(page, "撤销")
    popover = page.locator(".ant-popconfirm:visible")
    expect(popover).to_contain_text("所有管理会话")
    expect(popover.get_by_role("button", name="确认撤销", exact=True)).to_have_class(re.compile(r"ant-btn-dangerous"))
    button(popover, "取消")
    assert browser.posts(f"/{key_id}/revoke") == 0
    assert query(app, "SELECT revoked_at FROM admin_passkey")[0]["revoked_at"] is None
    assert len(query(app, "SELECT id FROM admin_audit")) == 1
    button(page, "撤销")
    button(page.locator(".ant-popconfirm:visible"), "确认撤销")
    expect(page.get_by_role("heading", name="管理员登录", exact=True)).to_be_visible()
    assert browser.posts(f"/{key_id}/revoke") == 1
    assert query(app, "SELECT revoked_at FROM admin_passkey")[0]["revoked_at"] is not None
    assert query(app, "SELECT COUNT(*) AS n FROM admin_session WHERE revoked_at IS NULL")[0]["n"] == 0
    assert [r["action"] for r in query(app, "SELECT action FROM admin_audit ORDER BY id")] == [
        "auth.passkey.register", "auth.passkey.revoke",
    ]

    app.test_clock[0] += timedelta(seconds=30)
    browser.login()
    browser.keys()
    expect(page.get_by_text("暂无通行密钥", exact=True)).to_be_visible()
    assert [r["result"] for r in query(app, "SELECT result FROM admin_login_event ORDER BY id")] == ["success"] * 3
    audit_from_ui(browser, "auth.passkey.register", "登记通行密钥")
    audit_from_ui(browser, "auth.passkey.revoke", "撤销通行密钥")
    browser.capture("03-revoke-audit-1280.png", 1280, 720)


@pytest.mark.parametrize("mode", ["register", "login"])
def test_cancelled_authenticator_recovers_without_finish(passkey_browser, mode):
    browser = passkey_browser
    page, app = browser.page, browser.app
    method = "create" if mode == "register" else "get"
    if mode == "register":
        browser.login()
        browser.keys()
        label = "登记通行密钥"
    else:
        page.goto(browser.origin + "/login", wait_until="networkidle")
        label = "使用通行密钥登录"
    sessions_before = len(query(app, "SELECT id FROM admin_session"))
    events_before = len(query(app, "SELECT id FROM admin_login_event"))
    page.evaluate("""method => {
        window.restoreCredential = navigator.credentials[method].bind(navigator.credentials);
        navigator.credentials[method] = async () => { throw new DOMException('isolated cancellation', 'NotAllowedError'); };
    }""", method)
    button(page, label)
    expect(page.get_by_role("alert")).to_contain_text(CANCELLED)
    trigger = page.get_by_role("button", name=label, exact=True)
    expect(trigger).to_be_enabled()
    expect(trigger).not_to_have_class(BUSY)
    assert browser.posts(f"/{mode}/options") == 1
    assert browser.posts(f"/{mode}/finish") == 0
    assert not query(app, "SELECT id FROM admin_passkey")
    assert not query(app, "SELECT id FROM admin_audit")
    assert len(query(app, "SELECT id FROM admin_session")) == sessions_before
    assert len(query(app, "SELECT id FROM admin_login_event")) == events_before
    browser.capture(f"cancel-{mode}-1280.png", 1280, 720)
    page.evaluate("method => { navigator.credentials[method] = window.restoreCredential; delete window.restoreCredential; }", method)
    if mode == "register":
        register(browser)
    else:
        browser.login()
