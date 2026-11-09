"""正式Umi页面的业务回归辅助；只用专属临时库与正常页面/真实接口。"""
import re
import uuid
from tests.test_admin_auth import query
from tests.test_admin_browser import button,expect


def choose(page,label,needle):
    page.get_by_label(label,exact=True).click()
    root=getattr(page,'page',page)
    root.locator('.ant-select-dropdown:visible .ant-select-item-option').filter(has_text=needle).first.click()


def save_dialog(page,title,submit=None):
    labels={'安装芯片':'确认安装','启用物品档案':'确认启用物品','停用物品档案':'确认停用物品','维护售出事实':'保存售出确认','准备替换物品':'保存新物品准备','准备转售的新整套物品':'保存新物品准备','确认发行约定':'确认发行约定','登记数字物品':'登记并查看物品'}
    dialog=page.get_by_role('dialog',name=title,exact=True);button(dialog,submit or labels.get(title,'保存'));dialog.wait_for(state='hidden')


def api(desktop,action,payload):
    p=desktop.page
    session=p.request.get('http://localhost:5174/api/admin/auth/session').json()['data']
    response=p.request.post('http://localhost:5174/api/admin/catalog/actions/'+action,headers={'Origin':'http://localhost:5174','X-CSRF-Token':session['csrf_token']},data={'request_id':str(uuid.uuid4()),'payload':payload})
    assert response.status==200,response.json()
    return response.json()['data']


def install(desktop,style,item,chip,spec='L黑'):
    physical=api(desktop,'createPhysicalItem',{'style_id':style,'physical_uid':'PHY-'+uuid.uuid4().hex,'spec':spec})['id']
    return api(desktop,'installAssembly',{'item_id':item,'physical_item_id':physical,'chip_id':chip,'installed':True})


def setup(desktop,*,validation=False):
    from tests.test_chip_keys import configure
    configure(desktop.app);desktop.login()
    style=api(desktop,'style',{'project':'fashion','code':'UI-CAP','name':'浏览器共用帽子','specs':['L黑'],'image_urls':[]})['id']
    issue=api(desktop,'issue',{'style_id':style,'name':'浏览器限定发行','mode':'fixed','total':50,'rights':['renewal','resale'],'description':'整套换新、转售，身份编号延续'})['id']
    api(desktop,'confirmIssue',{'issue_id':issue})
    item=api(desktop,'item',{'issue_id':issue,'item_uid':'FASH-2026-880001','edition_number':1,'is_validation':validation})['id']
    chips=[api(desktop,'register',{'chip_uid':f'04{n:012X}'})['id'] for n in (201,202,203)]
    return style,issue,item,chips


def key_configuration(desktop,chip_id):
    from core.chip_keys import target_keys
    from tests.test_chip_keys import reading
    p=desktop.page;d=p.get_by_role('dialog',name='密钥与配置',exact=True)
    button(d,'生成密钥');expect(d.get_by_text('密钥已生成',exact=False).first).to_be_visible()
    uid=query(desktop.app,'SELECT chip_uid FROM chip WHERE id=%s',(chip_id,))[0]['chip_uid']
    with desktop.app.app_context():keys=target_keys('fashion',uid)
    for n,counter in enumerate((3,4),1):
        r=reading(keys,uid,counter)
        d.get_by_label(f'第{n}条触碰链接',exact=True).fill('https://nfc.bumbum.cc/tap?picc_data='+r['picc_data']+'&cmac='+r['cmac'])
    d.get_by_role('checkbox').last.check();button(d,'确认配置核验')
    expect(d.get_by_text('配置已核验',exact=False).first).to_be_visible();d.get_by_role('button',name=re.compile(r'^关\s*闭$')).last.click();d.wait_for(state='hidden')
