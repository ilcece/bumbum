"""真实浏览器显式检查React 19补丁；独立页面不使用业务数据库。"""

from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request

from PIL import Image
import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.browser
SOURCE = Path(__file__).parent / 'fixtures' / 'antd_compatibility'


@pytest.fixture
def smoke(request):
    if not request.config.getoption('--browser'):
        pytest.skip('显式启用--browser后才启动组件冒烟')
    project = Path(os.getenv('BUMBUM_ANTD_PROJECT', str(SOURCE.parents[2] / 'frontend' / 'admin'))).resolve()
    vite = project / 'node_modules' / 'vite' / 'bin' / 'vite.js'
    if not vite.is_file():
        pytest.fail('组件冒烟需要已严格安装候选依赖的管理工程或BUMBUM_ANTD_PROJECT临时副本')
    with tempfile.TemporaryDirectory(prefix='.antd-smoke-', dir=project) as directory:
        root = Path(directory)
        for path in SOURCE.iterdir():
            shutil.copy2(path, root / path.name)
        with socket.socket() as candidate:
            candidate.bind(('127.0.0.1', 0))
            port = candidate.getsockname()[1]
        with (root / 'vite.log').open('w') as log:
            process = subprocess.Popen(['node', str(vite), str(root), '--config', str(root / 'vite.config.mjs'), '--host', '127.0.0.1', '--port', str(port), '--strictPort'], cwd=project, stdout=log, stderr=log)
            try:
                url = f'http://127.0.0.1:{port}'
                for _ in range(100):
                    try:
                        urllib.request.urlopen(url, timeout=.3).close()
                        break
                    except OSError:
                        if process.poll() is not None:
                            pytest.fail('隔离Vite启动失败：' + (root / 'vite.log').read_text()[-2000:])
                        time.sleep(.1)
                else:
                    pytest.fail('隔离组件页面未在10秒内就绪')
                with sync_playwright() as playwright:
                    executable = request.config.getoption('--browser-executable')
                    browser = playwright.chromium.launch(**({'executable_path': executable} if executable else {}))
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    failures = []
                    page.on('pageerror', lambda error: failures.append(str(error)))
                    def console(message):
                        known_static_limit = bool(re.fullmatch(r"Warning: \[antd: (Modal|notification)\] Static function can not consume context like dynamic theme\. Please use 'App' component instead\.", message.text))
                        if message.type == 'error' and not known_static_limit and '/_smoke/upload' not in message.location.get('url', ''):
                            failures.append(message.text)
                    page.on('console', console)
                    page.goto(url)
                    page.get_by_role('heading', name='隔离组件验证 · 合成数据').wait_for()
                    yield page
                    browser.close()
                    assert not failures, failures
            finally:
                process.terminate()
                process.wait(timeout=10)


@pytest.mark.parametrize('mode', ['static', 'app', 'hook'])
def test_modal_update_confirm_cancel_destroy_and_focus(smoke, mode):
    page = smoke
    trigger = page.get_by_role('button', name=f'{mode}打开弹层', exact=True)
    trigger.click()
    dialog = page.get_by_role('dialog')
    dialog.get_by_role('button', name='更新当前弹层').click()
    expect(dialog).to_contain_text('更新后的内容')
    dialog.get_by_role('button', name=re.compile(r'^确\s*认$')).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_role('status')).to_have_text(f'{mode}确认')
    expect(trigger).to_be_focused()
    trigger.click()
    page.get_by_role('dialog').get_by_role('button', name=re.compile(r'^取\s*消$')).click()
    expect(page.get_by_role('status')).to_have_text(f'{mode}取消')
    expect(page.get_by_role('dialog')).not_to_be_visible()
    trigger.click()
    page.get_by_role('dialog').get_by_role('button', name='销毁当前弹层').click()
    expect(page.get_by_role('dialog')).not_to_be_visible()
    expect(page.locator('.ant-modal-mask')).to_have_count(0)


@pytest.mark.parametrize('mode', ['static', 'app', 'hook'])
def test_notification_static_and_context_update_close_destroy(smoke, mode):
    page = smoke
    for action in ['open', 'success']:
        page.get_by_role('button', name=f'{mode}通知{action}', exact=True).click()
        expect(page.locator('.ant-notification-notice')).to_contain_text(f'{mode}通知')
        page.get_by_role('button', name=f'{mode}通知update', exact=True).click()
        expect(page.locator('.ant-notification-notice')).to_have_count(1)
        expect(page.locator('.ant-notification-notice')).to_contain_text('更新后的通知')
        page.locator('.ant-notification-notice-close').click()
        expect(page.locator('.ant-notification-notice')).to_have_count(0)
    page.get_by_role('button', name=f'{mode}通知open', exact=True).click()
    page.get_by_role('button', name=f'{mode}通知destroy', exact=True).click()
    expect(page.locator('.ant-notification-notice')).to_have_count(0)


@pytest.mark.parametrize('mode', ['成功', '失败', '延迟后成功'])
def test_upload_real_callbacks_controlled_list_and_abort(smoke, mode):
    page = smoke
    page.get_by_role('combobox', name='上传结果', exact=True).press('ArrowDown')
    page.get_by_text(mode, exact=True).last.click()
    buffer = BytesIO()
    Image.new('RGB', (2, 2), 'blue').save(buffer, format='PNG')
    page.locator('input[type=file]').set_input_files({'name': 'synthetic.png', 'mimeType': 'image/png', 'buffer': buffer.getvalue()})
    if mode == '延迟后成功':
        expect(page.locator('.ant-upload-list-item-uploading')).to_have_count(1)
        page.locator('.ant-upload-list-item-actions button').click()
        page.wait_for_timeout(1500)
        expect(page.locator('.ant-upload-list-item')).to_have_count(0)
    else:
        expect(page.locator('.ant-upload-list-item-' + ('done' if mode == '成功' else 'error'))).to_have_count(1)
        expect(page.get_by_role('status')).to_have_text('上传回调' + ('成功' if mode == '成功' else '失败'))
        page.locator('.ant-upload-list-item-actions button').click()
        expect(page.locator('.ant-upload-list-item')).to_have_count(0)


def test_form_api_validation_scroll_readonly_reset_and_submit(smoke):
    page = smoke
    page.get_by_role('button', name='校验并定位').click()
    expect(page.get_by_role('status')).to_have_text('校验拒绝')
    expect(page.get_by_text('请填写名称', exact=True)).to_be_visible()
    expect(page.get_by_label('名称', exact=True)).to_be_focused()
    expect(page.get_by_text('04:A2:7F:1B:5E:80:00', exact=True)).to_be_visible()
    page.get_by_role('button', name='载入记录B').click()
    expect(page.get_by_label('名称', exact=True)).to_have_value('记录B')
    page.get_by_role('button', name='切换只读').click()
    expect(page.get_by_text('记录B', exact=True)).to_be_visible()
    expect(page.locator('input#compat_name')).to_have_count(0)
    page.get_by_role('button', name='切换只读').click()
    page.get_by_role('button', name='提交表单').click()
    expect(page.get_by_role('status')).to_have_text('已提交:记录B')
    page.get_by_role('button', name='重置表单').click()
    expect(page.get_by_label('名称', exact=True)).to_have_value('')
    page.get_by_role('button', name='校验并定位').click()
    expect(page.get_by_role('status')).to_have_text('校验拒绝')
