"""按获认可原型更新的数字身份、整套换新转售及共用款图实际页面检查。"""
from io import BytesIO
import re
import pytest
from tests.test_admin_browser import browser_gate,desktop,button,expect
from tests.admin_ui_helpers import choose,save_dialog,setup,install,key_configuration
from tests.test_admin_auth import query
from tests.test_admin_catalog import owner
pytestmark=[pytest.mark.auth_database,pytest.mark.browser]


def fill_assembly(page,dialog,physical_uid,spec,chip_uid):
    button(dialog,'登记实体')
    register=page.get_by_role('dialog',name='登记实体物品',exact=True)
    register.get_by_label('实体编号',exact=True).fill(physical_uid)
    register.get_by_label('实际规格',exact=True).fill(spec)
    save_dialog(page,'登记实体物品')
    choose(dialog,'芯片 UID',chip_uid)
    dialog.get_by_role('checkbox',name=re.compile('已核对实体编号')).check()


def test_whole_item_from_preparation_through_loss_renewal_resale(desktop,tmp_path):
    _,_,item,chips=setup(desktop);p=desktop.page
    desktop.navigate('数字物品');button(p,'查看')
    drawer=p.get_by_role('dialog',name='数字物品详情',exact=True)
    button(drawer,'安装芯片');d=p.get_by_role('dialog',name='安装芯片',exact=True)
    fill_assembly(p,d,'PHY-BROWSER-FIRST','L黑','04:00:00:00:00:00:C9');save_dialog(p,'安装芯片')
    button(drawer,'预览手机页');preview=p.get_by_role('dialog',name=re.compile('手机页预览'))
    expect(preview.get_by_text('只读预览 · 状态与账户为模拟',exact=True)).to_be_visible()
    preview.get_by_text('待认领',exact=True).click();button(preview,'查看下一步');expect(preview.get_by_text('手机号验证',exact=True)).to_be_visible()
    preview.get_by_text('持有人',exact=True).click();expect(preview.get_by_text('模拟账户 138****0000',exact=True)).to_be_visible()
    preview.get_by_role('button',name=re.compile(r'关\s*闭')).click();preview.wait_for(state='hidden')
    button(drawer,'查看密钥与配置');key_configuration(desktop,chips[0])
    button(drawer,'启用物品');save_dialog(p,'启用物品档案')
    button(drawer,'维护售出事实');d=p.get_by_role('dialog',name='维护售出事实');d.get_by_label('销售确认或更正依据',exact=True).fill('外部平台实际售出');save_dialog(p,'维护售出事实')
    a=owner(desktop.app,item,21);b=owner(desktop.app,None,22)
    button(p,'打开完整详情');p.reload(wait_until='networkidle')
    expect(p.get_by_text('139****0021',exact=True)).to_be_visible()
    assert p.get_by_text('13900000021',exact=True).count()==0
    button(p,'查看完整手机号')
    phone=p.get_by_role('dialog',name='完整手机号',exact=True)
    expect(phone.get_by_text('13900000021',exact=True)).to_be_visible()
    phone.get_by_role('button',name=re.compile(r'^关\s*闭$')).last.click()
    phone.wait_for(state='hidden')
    assert p.get_by_text('13900000021',exact=True).count()==0
    button(p,'办理换新');d=p.get_by_role('dialog',name='准备替换物品');fill_assembly(p,d,'PHY-BROWSER-RENEW','新实物L黑','04:00:00:00:00:00:CA');d.get_by_label('核对依据',exact=True).fill('核对年度资格');save_dialog(p,'准备替换物品')
    w=p.get_by_role('dialog',name='定期换新 · 整套物品办理');button(w,'查看密钥与配置');key_configuration(desktop,chips[1]);button(w,'关闭，保留办理记录');w.wait_for(state='hidden')
    button(p,'挂失物品');d=p.get_by_role('dialog',name='挂失物品',exact=True);d.get_by_label('核对依据',exact=True).fill('整套丢失，已核对原持有人');save_dialog(p,'挂失物品','确认挂失整套物品')
    expect(p.get_by_text('当前整套物品已挂失',exact=True)).to_be_visible()
    button(p,'继续办理换新');w=p.get_by_role('dialog',name='挂失换新 · 整套物品办理');w.get_by_label('实际交付核对依据',exact=True).fill('已交付新实物及配套芯片');w.get_by_role('checkbox').check()
    p.screenshot(animations='disabled',path=str(tmp_path/'whole-renewal-1280.png'))
    button(w,'确认交付并生效');w.wait_for(state='hidden');expect(p.get_by_text('第2代物品',exact=True)).to_be_visible()
    button(p,'办理转售');d=p.get_by_role('dialog',name='准备转售的新整套物品');fill_assembly(p,d,'PHY-BROWSER-RESALE','转售新整套','04:00:00:00:00:00:CB');choose(d,'已核对接收账户','临时账户22');d.get_by_label('核对依据',exact=True).fill('核对新接收账户');d.get_by_label('原持有人确认依据',exact=True).fill('已确认转出');d.get_by_label('接收人确认依据',exact=True).fill('已确认接收');save_dialog(p,'准备转售的新整套物品')
    w=p.get_by_role('dialog',name='后台转售 · 整套物品办理');button(w,'查看密钥与配置');key_configuration(desktop,chips[2]);w.get_by_label('实际交付核对依据',exact=True).fill('转售新整套已交付');w.get_by_role('checkbox').check();button(w,'确认交付并生效');w.wait_for(state='hidden')
    expect(p.get_by_text('第3代物品',exact=True)).to_be_visible()
    actual=query(desktop.app,'SELECT i.item_uid,d.edition_number,o.user_id FROM item i JOIN digital_item d ON d.item_id=i.id JOIN ownership o ON o.active_item_id=i.id WHERE i.id=%s',(item,))[0]
    assert actual=={'item_uid':'FASH-2026-880001','edition_number':1,'user_id':b}
    assert len(query(desktop.app,'SELECT * FROM whole_item WHERE item_id=%s',(item,)))==3
    p.get_by_role('button',name=re.compile('物品办理记录')).click()
    row=p.locator('.ant-table-tbody tr').filter(has_text='挂失换新').first
    button(row,'查看');historic=p.get_by_role('dialog',name='挂失换新 · 整套物品办理')
    expect(historic.get_by_text('04:00:00:00:00:00:C9',exact=True)).to_be_visible();expect(historic.get_by_text('04:00:00:00:00:00:CA',exact=True)).to_be_visible();assert historic.get_by_text('04:00:00:00:00:00:CB',exact=True).count()==0
    p.screenshot(animations='disabled',path=str(tmp_path/'whole-history-correspondence.png'))
    button(historic,'关闭，保留办理记录');historic.wait_for(state='hidden')
    p.screenshot(animations='disabled',path=str(tmp_path/'whole-resale-completed.png'),full_page=True)


def test_shared_images_real_upload_preview_and_save(desktop,tmp_path):
    from PIL import Image
    style,_,item,_=setup(desktop);desktop.app.config['MEDIA_ENABLED']=False;p=desktop.page
    desktop.navigate('款式与发行');button(p,'维护资料');d=p.get_by_role('dialog',name='维护款式共用资料')
    image=BytesIO();Image.new('RGB',(32,24),'blue').save(image,format='PNG')
    d.locator('input[type=file]').set_input_files({'name':'synthetic.png','mimeType':'image/png','buffer':image.getvalue()})
    expect(d.get_by_alt_text('商品图片 1',exact=True)).to_be_visible()
    assert query(desktop.app,'SELECT COUNT(*) AS n FROM style_image')[0]['n']==0
    d.get_by_label('款式名称',exact=True).fill('已保存共用帽子');button(d,'保存共用资料');button(p.get_by_role('dialog',name='确认同步共用商品资料？',exact=True),'确认同步保存')
    expect(d.get_by_text('款式资料已保存，仍有图片待保存；请继续完成或明确放弃未保存部分。',exact=True)).to_be_visible()
    assert query(desktop.app,'SELECT COUNT(*) AS n FROM style_image')[0]['n']==0
    desktop.app.config['MEDIA_ENABLED']=True
    button(d,'保存共用资料');button(p.get_by_role('dialog',name='确认同步共用商品资料？',exact=True),'确认同步保存');d.wait_for(state='hidden')
    p.goto(f'http://localhost:5174/items/{item}',wait_until='networkidle');expect(p.get_by_text('已保存共用帽子',exact=True)).to_be_visible()
    p.screenshot(animations='disabled',path=str(tmp_path/'shared-style-item.png'))
    assert query(desktop.app,'SELECT COUNT(*) AS n FROM style_image WHERE style_id=%s',(style,))[0]['n']==1


def test_new_style_issue_and_identity_entirely_through_ui(desktop,tmp_path):
    desktop.login();p=desktop.page;p.set_viewport_size({'width':1440,'height':900});desktop.navigate('款式与发行')
    button(p,'新建款式');expect(p.get_by_label('款式编号',exact=True)).to_be_visible();d=p;d.get_by_label('款式编号',exact=True).fill('UI-ALL');d.get_by_label('款式名称',exact=True).fill('从头创建帽子');button(p,'保存共用资料');p.wait_for_url(re.compile(r'/catalog/style/[0-9]+(?:\?.*)?$'));desktop.navigate('款式与发行')
    p.get_by_role('tab',name='发行约定',exact=True).click();button(p,'新增发行约定');expect(p.get_by_label('发行名称',exact=True)).to_be_visible();d=p;choose(d,'关联款式','从头创建帽子');d.get_by_label('发行名称',exact=True).fill('首个固定发行');d.get_by_label('固定发行总量',exact=True).fill('50');d.get_by_label('发行说明与规格承诺',exact=True).fill('仅限50个数字身份，实物换新不增发');expect(d.get_by_label('适用权益',exact=True)).to_have_count(0);button(p,'保存发行草案');p.wait_for_url(re.compile(r'/catalog/issue/[0-9]+(?:\?.*)?$'))
    button(p,'确认发行约定');save_dialog(p,'确认发行约定');expect(p.get_by_text('已确认',exact=True).first).to_be_visible()
    desktop.navigate('数字物品');button(p,'登记数字物品');d=p.get_by_role('dialog',name='登记数字物品');choose(d,'关联发行约定','首个固定发行');d.get_by_label('系统物品编号',exact=True).fill('FASH-2026-888999');d.get_by_label('本件正式序号',exact=True).fill('1');save_dialog(p,'登记数字物品')
    d=p.get_by_role('dialog',name='数字物品详情');expect(d.get_by_text('#01/50',exact=True)).to_be_visible();expect(d.get_by_text('从头创建帽子',exact=True)).to_be_visible();p.screenshot(animations='disabled',path=str(tmp_path/'new-item-1440.png'))
    assert query(desktop.app,'SELECT COUNT(*) AS n FROM item')[0]['n']==1


def test_direct_style_detail_and_item_chip_return(desktop):
    style,_,item,chips=setup(desktop);p=desktop.page
    install(desktop,style,item,chips[0])
    p.goto(f'http://localhost:5174/catalog/style/{style}',wait_until='networkidle');expect(p.get_by_label('款式名称',exact=True)).to_have_value('浏览器共用帽子');button(p,'取消');expect(p).to_have_url(re.compile(r'/catalog(?:\?tab=styles)?$'))
    p.goto(f'http://localhost:5174/items/{item}',wait_until='networkidle');button(p,'04:00:00:00:00:00:C9');expect(p).to_have_url(re.compile(f'/chips/{chips[0]}\\?from='));p.get_by_role('button',name='back',exact=True).click();expect(p).to_have_url(re.compile(f'/items/{item}$'))
