"""桌面浏览器夹具只接收auth_database生成的专属临时库。"""

from datetime import timezone
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading

import pyotp
import pytest
from werkzeug.serving import make_server, WSGIRequestHandler

from core.db import get_database

ROOT = Path(__file__).resolve().parents[1]


def frontend_ready(output):
    """忽略终端颜色码，仍只识别本次Vite日志中的固定本地地址。"""
    plain = re.sub(r'\x1b\[[0-9;]*m', '', output)
    return 'http://127.0.0.1:5174/' in plain or 'http://localhost:5174/' in plain


class QuietHandler(WSGIRequestHandler):
    def log(self, *args):
        pass


class BrowserSession:
    """凭证只用于登录调用，不提供包含凭证的repr或网络记录。"""
    def __init__(self, page, app, account):
        self.page, self.app, self._account = page, app, account

    def __repr__(self):
        return '<isolated browser session>'

    def login(self):
        page = self.page
        page.goto('http://localhost:5174', wait_until='networkidle')
        page.get_by_label('账号', exact=True).fill(self._account['username'])
        page.get_by_label('密码', exact=True).fill(self._account['password'])
        clock = self.app.test_clock[0].replace(tzinfo=timezone.utc).timestamp()
        page.get_by_label('Authenticator 验证码', exact=True).fill(pyotp.TOTP(self._account['secret']).at(clock))
        page.get_by_role('button', name='登录', exact=True).click()
        page.get_by_role('heading', name='你好，cece', exact=True).wait_for()

    def navigate(self, name):
        self.page.get_by_role('navigation', name='基础功能').get_by_role('button', name=name, exact=True).click()


def assert_ports_available(ports=(5000, 5174)):
    for port in ports:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                pytest.fail('浏览器测试端口被占用；未接管现有服务，请先停止自己的开发服务。')


def browser_fixture(request, app, account, tmp_path):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.fail('请先按联调手册安装requirements-browser.txt及Chromium，未跳过浏览器检查。')
    assert_ports_available()
    if not shutil.which('node') or not (ROOT/'frontend/admin/node_modules/vite/bin/vite.js').is_file():
        pytest.fail('请先准备Node和前端依赖；未启动或接管任何已有服务。')
    with app.app_context():
        conn = get_database()
        with conn.cursor() as cursor:
            for table in ('fashion_item_profile','jewelry_item_profile','item'):
                cursor.execute(f'DELETE FROM {table}')
        conn.commit()
    server = make_server('127.0.0.1', 5000, app, threaded=True, request_handler=QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    frontend = None
    with open(tmp_path/'frontend.log', 'w', encoding='utf-8') as output:
        try:
            frontend = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js'], cwd=ROOT/'frontend/admin', stdout=output, stderr=output)
            with sync_playwright() as playwright:
                options = {'headless': True}
                executable = request.config.getoption('--browser-executable')
                if executable:
                    options['executable_path'] = executable
                browser = playwright.chromium.launch(**options)
                page = browser.new_page(viewport={'width':1280,'height':720})
                page.set_default_timeout(12000)
                failures = []
                page.on('pageerror', lambda error: failures.append(type(error).__name__))
                try:
                    # 只等待自己启动的Vite；端口预检已拒绝接管其他服务。
                    for _ in range(150):
                        if frontend.poll() is not None:
                            pytest.fail('本次前端启动失败，请核对Node与锁定依赖；日志不包含认证请求。')
                        ready = (tmp_path/'frontend.log').read_text(encoding='utf-8', errors='replace')
                        if not frontend_ready(ready):
                            threading.Event().wait(.1)
                            continue
                        try:
                            page.goto('http://localhost:5174', timeout=1000)
                            break
                        except Exception:
                            threading.Event().wait(.1)
                    else:
                        pytest.fail('本次前端在限定时间内未就绪。')
                    yield BrowserSession(page, app, account)
                    assert not failures, '浏览器出现未捕获错误；只报告类型，未记录请求或控制台原文。'
                finally:
                    report = getattr(request.node, 'report_call', None)
                    if (report and report.failed) or failures or sys.exc_info()[0] is not None:
                        # 不保存HAR/trace/页面正文；截图前隐藏密码和动态验证码。
                        try:
                            page.locator('input[type="password"],input[name="code"]').evaluate_all('(nodes)=>nodes.forEach(node=>{node.value="";node.style.visibility="hidden"})')
                            base = Path(request.config.getoption('--browser-artifacts'))
                            if base.is_symlink():
                                raise ValueError('截图目录不可为符号链接')
                            base.mkdir(parents=True, exist_ok=True)
                            folder = Path(tempfile.mkdtemp(prefix='browser-', dir=base))
                            page.screenshot(path=str(folder/'failure.png'), full_page=True)
                        except Exception:
                            # 截图失败不覆盖原始测试失败。
                            pass
                    browser.close()
        finally:
            if frontend is not None:
                frontend.terminate()
                try:
                    frontend.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    frontend.kill(); frontend.wait(timeout=5)
            server.shutdown(); server.server_close(); thread.join(timeout=5)
