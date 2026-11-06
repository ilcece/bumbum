"""实际页面验证测试数据筛选、明细标记、统计与整批清理。"""
import pytest
from core.acceptance_data import seed
from core.db import get_database
from tests.test_admin_browser import desktop,browser_gate,button,expect
from tests.test_admin_auth import query

pytestmark=[pytest.mark.auth_database,pytest.mark.browser]

def test_batch_filter_statistics_cleanup_in_real_ui(desktop,monkeypatch,tmp_path):
    monkeypatch.setattr('core.test_batches.validate_test_target',lambda _:None)
    with desktop.app.test_request_context():result=seed(get_database(),desktop._account['username'],apply=True)
    p=desktop.page;desktop.login();batch=result['batch_id']
    p.goto(f'http://localhost:5174/items?data_scope=test&test_batch_id={batch}',wait_until='networkidle')
    expect(p.get_by_text('测试数据 · '+str(batch),exact=True).first).to_be_visible()
    p.locator('.ant-table-tbody tr').filter(has_text='JEW-').first.get_by_role('button',name='查看',exact=True).click()
    expect(p.get_by_text('本批包含合成配置、持有、交付及触碰样本',exact=False)).to_be_visible()
    p.screenshot(path=str(tmp_path/'test-item.png'),animations='disabled')
    p.goto(f'http://localhost:5174/overview?data_scope=test&test_batch_id={batch}',wait_until='networkidle')
    expect(p.get_by_text('当前统计含测试数据',exact=False)).to_be_visible()
    p.screenshot(path=str(tmp_path/'test-statistics.png'),animations='disabled')
    p.get_by_label('数据范围',exact=True).click();p.get_by_text('业务数据',exact=True).last.click()
    expect(p.get_by_text('当前没有业务数据',exact=False)).to_be_visible()
    desktop.navigate('系统管理');p.get_by_role('tab',name='测试数据',exact=True).click();button(p,'清理本批数据')
    d=p.get_by_role('dialog',name='确认整批清理',exact=True);expect(d).to_be_visible();d.get_by_role('checkbox').check()
    p.screenshot(path=str(tmp_path/'test-cleanup.png'),animations='disabled');button(d,'确认清理本批数据');d.wait_for(state='hidden')
    expect(p.get_by_text('已清理',exact=True)).to_be_visible()
    assert query(desktop.app,'SELECT COUNT(*) AS n FROM test_batch WHERE status=\'deleted\'')[0]['n']==1
