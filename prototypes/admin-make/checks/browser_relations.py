"""验证共用资料引用、芯片项目来源和新入口，不调用真实业务接口。"""
import json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
url=sys.argv[1];out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]
def passed(text):checks.append({'case':text,'status':'passed'});print('通过：'+text,flush=True)
def raw(page):return page.evaluate("JSON.parse(sessionStorage.getItem('bumbum-make-prototype-v2'))")
def modal(page):return page.locator('.ant-modal:visible').last
def menu(page,name):page.get_by_role('menuitem',name=re.compile(name)).click()
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1600,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
 try:
  page.goto(url,wait_until='networkidle');page.get_by_role('button',name='使用演示身份进入').click()
  d=raw(page);assert all('project' not in c and 'item_uid' not in c for c in d['chips']);assert all('profile' not in i and 'sku_code' not in i for i in d['items']);assert d['items'][0]['styleId']==d['items'][1]['styleId'];history=d['identities'];style=d['styles'][0]
  passed('芯片不存独立项目；物品只存款式引用，不复制共用资料')
  menu(page,'数字物品管理');page.get_by_role('button',name='款式与发行资料',exact=True).click();m=modal(page);expect(m.get_by_text('款式商品资料',exact=True)).to_be_visible();m.get_by_role('button',name='维护共用资料',exact=True).first.click();e=modal(page);e.get_by_label('名称',exact=True).fill('统一更新的款式');e.get_by_role('button',name='保存共用资料',exact=True).click();modal(page).get_by_role('button',name='确认同步保存',exact=True).click();page.wait_for_timeout(450);d=raw(page);saved=next(s for s in d['styles'] if s['id']==style['id']);assert saved['profile']['name']=='统一更新的款式';assert saved['profile']['size_chart']==style['profile']['size_chart'];assert saved['sizes']==style['sizes'];assert d['identities']==history
  passed('共用保存更新唯一资料，折叠尺码资料与独立实体/权益历史完整保留')
  modal(page).get_by_role('button',name='新建款式资料',exact=True).click();e=modal(page);e.get_by_label('款式编号',exact=True).fill('DEMO-SHARED-NEW');e.get_by_label('名称',exact=True).fill('新建共用款式');e.get_by_role('button',name='保存共用资料',exact=True).click();page.wait_for_timeout(350);assert any(s['code']=='DEMO-SHARED-NEW' for s in raw(page)['styles']);passed('共用款式有独立新建维护入口')
  modal(page).get_by_role('tab',name='发行记录',exact=True).click();expect(modal(page).get_by_role('button',name='新建发行记录（编号范围待确认）',exact=True)).to_be_disabled();modal(page).get_by_role('button',name='查看发行约定',exact=True).click();expect(modal(page).get_by_label('发行总量',exact=True)).to_be_disabled();page.get_by_role('dialog',name='查看发行约定',exact=True).get_by_role('button',name=re.compile(r'^关\s*闭$')).last.click();expect(page.get_by_role('dialog',name='查看发行约定',exact=True)).to_be_hidden();page.get_by_role('dialog',name='款式与发行资料',exact=True).get_by_role('button',name=re.compile(r'^关\s*闭$')).last.click();passed('已发行约定只读，待确认的编号范围不擅自生效')
  menu(page,'芯片管理');page.get_by_role('button',name=re.compile('手工登记芯片$')).click();m=modal(page);expect(m.get_by_text('所属项目',exact=True)).to_have_count(0);m.get_by_role('switch').check();m.get_by_placeholder('如 04:A2:7F:1B:5E:80:18 或 04a27f1b5e8018').fill('04:AA:BB:CC:DD:EE:78');m.get_by_role('button',name='登记并继续下一枚',exact=True).click();page.wait_for_timeout(200);c=next(c for c in raw(page)['chips'] if c['chip_uid']=='04:AA:BB:CC:DD:EE:78');assert c['is_validation_object'] is True and 'project' not in c;passed('芯片登记无项目字段，验证标记可用且不写独立项目')
  m.get_by_role('button',name=re.compile(r'^取\s*消$')).click();page.get_by_role('button',name='04:AA:BB:CC:DD:EE:78',exact=True).click();drawer=page.locator('.ant-drawer:visible');expect(drawer.get_by_text('未关联物品',exact=True).first).to_be_visible();assert round(drawer.locator('.ant-drawer-content-wrapper').bounding_box()['width'])==800;expect(drawer.get_by_role('switch').first).to_be_enabled();page.screenshot(path=str(out/'chip-reference.png'));passed('芯片详情800px，未关联物品时不虚构项目，未配置标记可维护')
  assert not errors,errors
 except Exception as exc:
  page.screenshot(path=str(out/'relations-failure.png'));checks.append({'case':'当前路径','status':'failed','error':str(exc)});raise
 finally:
  (out/'browser-relations.json').write_text(json.dumps({'results':checks,'page_errors':errors},ensure_ascii=False,indent=2));b.close()
