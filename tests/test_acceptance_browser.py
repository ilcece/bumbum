"""实际页面验证原型布局、全局测试开关、真实保存与整批清理。"""
from pathlib import Path
import pytest
from core.acceptance_data import seed
from core.db import get_database
from tests.test_admin_browser import desktop,browser_gate,button,expect
from tests.test_admin_auth import query

pytestmark=[pytest.mark.auth_database,pytest.mark.browser]

def test_batch_filter_statistics_cleanup_in_real_ui(desktop,monkeypatch,tmp_path):
    monkeypatch.setattr('core.test_batches.validate_test_target',lambda _:None)
    with desktop.app.test_request_context():result=seed(get_database(),desktop._account['username'],apply=True)
    evidence=Path('test-results/admin-fidelity');evidence.mkdir(parents=True,exist_ok=True)
    p=desktop.page;desktop.login();batch=result['batch_id']
    p.goto('http://localhost:5174/system?tab=settings',wait_until='networkidle')
    p.get_by_role('switch',name='开启测试数据',exact=True).check()
    p.wait_for_load_state('networkidle')
    desktop.navigate('数字物品')
    expect(p.get_by_label('数据范围',exact=True)).to_have_count(0)
    expect(p.get_by_text('数据来源',exact=True)).to_have_count(0)
    p.locator('.ant-table-tbody tr').filter(has_text='JEW-').first.get_by_role('button',name='查看',exact=True).click()
    expect(p.get_by_text('测试数据已开启',exact=True)).to_be_visible()
    p.wait_for_load_state('networkidle')
    p.screenshot(path=str(evidence/'restored-item-detail.png'),full_page=True,animations='disabled')
    desktop.navigate('工作台')
    expect(p.get_by_text('物品与芯片概况',exact=True)).to_be_visible()
    expect(p.get_by_text('触碰统计',exact=True)).to_be_visible()
    expect(p.get_by_label('数据范围',exact=True)).to_have_count(0)
    p.set_viewport_size({'width':1440,'height':900})
    p.wait_for_load_state('networkidle')
    p.screenshot(path=str(evidence/'restored-overview.png'),full_page=True,animations='disabled')
    desktop.navigate('数字物品')
    p.wait_for_load_state('networkidle')
    p.screenshot(path=str(evidence/'restored-items.png'),full_page=True,animations='disabled')
    desktop.navigate('芯片管理')
    expect(p.get_by_role('button',name='密钥与配置',exact=True).first).to_be_visible()
    expect(p.get_by_label('数据范围',exact=True)).to_have_count(0)
    p.wait_for_load_state('networkidle')
    p.screenshot(path=str(evidence/'restored-chips.png'),full_page=True,animations='disabled')
    desktop.navigate('款式与发行')
    expect(p.get_by_role('button',name='新建款式',exact=True)).to_be_visible()
    expect(p.locator('.ant-table-tbody tr').filter(has_text='验收').first).to_be_visible()
    expect(p.get_by_label('数据范围',exact=True)).to_have_count(0)
    p.wait_for_load_state('networkidle')
    p.screenshot(path=str(evidence/'restored-catalog.png'),full_page=True,animations='disabled')
    p.get_by_role('button',name='新建款式',exact=True).click()
    expect(p.get_by_label('款式编号',exact=True)).to_be_visible()
    expect(p.get_by_role('dialog')).to_have_count(0)
    expect(p.get_by_label('测试批次',exact=True)).to_have_count(0)
    p.wait_for_load_state('networkidle')
    p.screenshot(path=str(evidence/'restored-style-new.png'),full_page=True,animations='disabled')
    p.get_by_label('款式编号',exact=True).fill('BROWSER-REAL-STYLE')
    p.get_by_label('款式名称',exact=True).fill('接口保存款式')
    button(p,'保存')
    p.wait_for_url(__import__('re').compile(r'/catalog/style/[0-9]+$'))
    p.wait_for_load_state('networkidle')
    created=query(desktop.app,"SELECT id FROM product_style WHERE code='BROWSER-REAL-STYLE'")[0]['id']
    assert query(desktop.app,"SELECT batch_id FROM test_batch_object WHERE kind='style' AND object_id=%s",(created,))[0]['batch_id']==batch
    desktop.navigate('工作台')
    p.get_by_role('button',name='登记数字物品',exact=True).click()
    expect(p.get_by_role('alert').filter(has_text='不支持')).to_have_count(0)
    dialog=p.get_by_role('dialog',name='新建数字物品身份',exact=True)
    expect(dialog).to_be_visible()
    p.set_viewport_size({'width':1280,'height':720})
    p.screenshot(path=str(evidence/'restored-create-small.png'),animations='disabled')
    button(dialog,'取消')
    desktop.navigate('系统管理');p.get_by_role('tab',name='设置',exact=True).click()
    p.get_by_role('switch',name='开启测试数据',exact=True).uncheck()
    p.wait_for_load_state('networkidle');desktop.navigate('数字物品')
    expect(p.get_by_text('JEW-',exact=False)).to_have_count(0)
    desktop.navigate('系统管理');p.get_by_role('tab',name='设置',exact=True).click();button(p,'清理本批数据')
    d=p.get_by_role('dialog',name='确认整批清理',exact=True);expect(d).to_be_visible();d.get_by_role('checkbox').check()
    p.screenshot(path=str(tmp_path/'test-cleanup.png'),animations='disabled');button(d,'确认清理本批数据');d.wait_for(state='hidden')
    expect(p.get_by_text('已清理',exact=True)).to_be_visible()
    assert query(desktop.app,'SELECT COUNT(*) AS n FROM test_batch WHERE status=\'deleted\'')[0]['n']==1
