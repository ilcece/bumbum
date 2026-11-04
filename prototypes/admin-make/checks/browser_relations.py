"""定向验证批准后的业务架构、类别引用、发行草案、办理状态及Webhook演示。"""
import json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
url=sys.argv[1];out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];requests=[]
def passed(name):checks.append({'case':name,'status':'passed'});print('通过：'+name,flush=True)
def raw(page):return page.evaluate("JSON.parse(sessionStorage.getItem('bumbum-make-prototype-v4'))")
def modal(page):return page.locator('.ant-modal:visible').last
def menu(page,name):page.get_by_role('menuitem',name=re.compile(name)).click()
def tab(page,name):page.get_by_role('tab',name=name,exact=True).click()
def select(page,locator,text):
 locator.click();page.locator('.ant-select-dropdown:visible').get_by_text(text,exact=True).last.click();expect(page.locator('.ant-select-dropdown:visible')).to_have_count(0)
def close_dialog(page,name):
 d=page.get_by_role('dialog',name=name,exact=True);d.get_by_role('button',name=re.compile(r'^关\s*闭$')).last.click();expect(d).to_be_hidden()
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1600,'height':1000});page.set_default_timeout(8000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url) if '/api/' in r.url else None)
 try:
  page.goto(url,wait_until='networkidle');page.get_by_role('button',name='使用演示身份进入').click();menu(page,'物品管理')
  for name in ['数字物品','款式资料','发行约定','办理记录']:expect(page.get_by_role('tab',name=name,exact=True)).to_be_visible()
  assert page.get_by_role('menuitem').count()==5;passed('5个一级入口与物品管理4个二级工作区')
  page.locator('.ant-pagination:visible').get_by_title('2',exact=True).click();page.get_by_role('button',name='FASH-2026-000121',exact=True).click();drawer=page.locator('.ant-drawer:visible');expect(drawer.get_by_role('button',name='维护共用资料',exact=True)).to_be_disabled();drawer.locator('.ant-drawer-close').click();expect(drawer).to_be_hidden();page.locator('.ant-pagination:visible').get_by_title('1',exact=True).click();passed('归档物品为只读样例，不开放普通编辑或恢复归档')
  d=raw(page);assert all('project' not in x for group in ['items','chips','issuances'] for x in d[group]);assert all(i['styleId'] for i in d['items']);passed('类别只存在款式，物品/发行/芯片不保存独立类别')
  history=d['identities'];style=d['styles'][0];tab(page,'款式资料');page.get_by_role('button',name='维护共用资料',exact=True).first.click();e=modal(page);expect(e.get_by_label('物品类别',exact=True)).to_be_disabled();expect(e.get_by_text('商品资料预览 · 未保存预览',exact=True)).to_be_visible();e.get_by_label('名称',exact=True).fill('统一维护的共用款式');e.get_by_role('button',name='保存共用资料',exact=True).click();c=page.locator('.ant-modal-confirm:visible').last;expect(c.get_by_text(re.compile('其中.*已启用'))).to_be_visible();c.get_by_role('button',name='确认同步保存',exact=True).click();expect(page.get_by_role('dialog',name='维护共用款式商品资料',exact=True)).to_be_hidden();saved=next(s for s in raw(page)['styles'] if s['id']==style['id']);assert saved['profile']['name']=='统一维护的共用款式';assert saved['profile']['size_chart']==style['profile']['size_chart'];assert saved['sizes']==style['sizes'];assert raw(page)['identities']==history;passed('共用保存提示影响及生效，更新不覆盖实体/年度/流转事实和折叠尺码字段')
  page.get_by_role('button',name='新建款式资料',exact=True).click();e=modal(page);select(page,e.get_by_label('物品类别',exact=True),'饰品');e.get_by_label('款式编号',exact=True).fill('DEMO-JEWELRY-NEW');e.get_by_label('名称',exact=True).fill('演示手串新款');e.get_by_role('button',name='保存共用资料',exact=True).click();expect(page.get_by_role('dialog',name='新建共用款式商品资料',exact=True)).to_be_hidden();assert next(s for s in raw(page)['styles'] if s['code']=='DEMO-JEWELRY-NEW')['project']=='jewelry';passed('未引用款式可选择类别，新款按饰品显示适用字段')
  tab(page,'数字物品');page.get_by_role('button',name=re.compile('创建物品草稿$')).click();e=modal(page);assert e.get_by_role('combobox').count()==1;select(page,e.get_by_role('combobox'),'DEMO-JEWELRY-NEW · 演示手串新款 · 饰品');expect(e.locator('input[readonly]')).to_have_value('饰品');uid=e.get_by_placeholder('JEW-2026-000003');uid.fill('JEW-2026-999901');e.get_by_role('button',name='创建并继续',exact=True).click();new=next(i for i in raw(page)['items'] if i['item_uid']=='JEW-2026-999901');assert new['styleId']==next(s for s in raw(page)['styles'] if s['code']=='DEMO-JEWELRY-NEW')['id'];e.get_by_role('button',name=re.compile(r'^取\s*消$')).click();passed('物品创建只选款式，类别只读引用且保存关联准确')
  tab(page,'发行约定');issued=raw(page)['issuances'][0];page.get_by_role('button',name='查看发行约定',exact=True).first.click();e=modal(page);expect(e.get_by_label('发行总量',exact=True)).to_be_disabled();expect(e.get_by_label('允许颜色及例外约定',exact=True)).to_have_value('黑色');expect(e.get_by_text('付费定期／挂失换新',exact=True)).to_be_visible();close_dialog(page,'查看发行约定');passed('已发行总量/颜色/权益版本只读，颜色取自发行而非当前实体')
  page.get_by_role('button',name='维护草案',exact=True).first.click();e=modal(page);e.get_by_label('发行说明与权益约定',exact=True).fill('演示同款再发行：蓝色；旧物品承诺不变');e.get_by_role('button',name='保存发行草案',exact=True).click();expect(page.get_by_role('dialog',name='维护发行草案',exact=True)).to_be_hidden();assert raw(page)['issuances'][0]==issued;assert raw(page)['issuances'][1]['status']=='draft';passed('发行草案可维护，保存不发行、不分配编号、不追改旧承诺')
  page.get_by_role('button',name='原型演示 · 样例数据',exact=True).click();page.get_by_role('menuitem',name='保存结果未知',exact=True).click();before=raw(page)['issuances'];page.get_by_role('button',name='维护草案',exact=True).first.click();e=modal(page);e.get_by_label('发行说明与权益约定',exact=True).fill('演示未知回执：输入保留');e.get_by_role('button',name='保存发行草案',exact=True).click();expect(e.get_by_role('button',name='保存发行草案',exact=True)).to_be_disabled();assert raw(page)['issuances']==before;e.get_by_role('button',name='〔演示〕核对并恢复',exact=True).click();e.get_by_role('button',name='保存发行草案',exact=True).click();expect(page.get_by_role('dialog',name='维护发行草案',exact=True)).to_be_hidden();passed('发行草案未知回执先核对，禁止重复保存，恢复后明确重试')
  tab(page,'办理记录')
  for phase in ['待准备','待发货','运输中','待交付核验','已完成','已取消历史','异常只读']:expect(page.get_by_text(phase,exact=True).first).to_be_visible()
  passed('办理列表覆盖准备、发货、运输、核验、完成、取消历史和异常只读状态')
  for workid,title in [('DEMO-RN-6','已取消历史 · 只读演示'),('DEMO-RN-7','异常办理 · 只读演示')]:
   row=page.get_by_role('row').filter(has_text=workid);row.get_by_role('button',name='查看记录',exact=True).click();e=page.get_by_role('dialog',name='业务办理',exact=True);expect(e.get_by_text(title,exact=True)).to_be_visible();expect(e.get_by_role('button',name='确认正式接续',exact=True)).to_have_count(0);e.locator('.ant-modal-close').click();expect(e).to_be_hidden()
  passed('取消与异常记录仅只读展示，没有擅自恢复/退款/接续操作')
  search=page.get_by_placeholder('办理编号、物品编号或名称');search.fill('DEMO-TR-3');search.press('Enter');page.get_by_role('button',name='继续办理',exact=True).click();e=page.get_by_role('dialog',name='业务办理',exact=True);expect(e.get_by_label('发货记录',exact=True)).to_be_disabled();expect(e.get_by_role('button',name='记录收到新实体',exact=True)).to_be_visible();e.locator('.ant-modal-close').click();expect(e).to_be_hidden();page.reload(wait_until='networkidle');page.get_by_role('button',name='使用演示身份进入').click();expect(page.get_by_role('tab',name='办理记录',exact=True)).to_have_attribute('aria-selected','true');expect(page.get_by_placeholder('办理编号、物品编号或名称')).to_have_value('DEMO-TR-3');passed('跨物品查询并继续运输中办理，刷新保留工作区/条件/已保存阶段')
  menu(page,'芯片管理');before=len(raw(page)['chips']);page.get_by_role('button',name='〔演示〕触发Webhook登记',exact=True).click();expect(page.get_by_text(re.compile('〔演示〕Webhook已登记'))).to_be_visible();d=raw(page);assert len(d['chips'])==before+1;c=d['chips'][0];assert c['registration_source']=='nfc_cool' and c['item_id'] is None and 'project' not in c;passed('标记明确的Webhook演示登记未关联芯片，不请求真实回调')
  page.get_by_role('button',name='〔演示〕重复回调',exact=True).click();expect(page.get_by_text(re.compile('重复回调命中原记录'))).to_be_visible();assert len(raw(page)['chips'])==before+1;page.get_by_role('button',name='〔演示〕鉴权失败',exact=True).click();expect(page.get_by_text(re.compile('Webhook鉴权失败，未登记'))).to_be_visible();assert len(raw(page)['chips'])==before+1;passed('重复回调不重复造卡，鉴权失败不登记或覆盖数据')
  page.screenshot(path=str(out/'webhook-demo.png'));assert not errors,errors;assert not requests,requests;passed('架构与演示路径无页面运行异常、无真实业务API请求')
 except Exception as exc:
  page.screenshot(path=str(out/'architecture-failure.png'));checks.append({'case':'当前路径','status':'failed','error':str(exc)});raise
 finally:
  (out/'browser-relations.json').write_text(json.dumps({'results':checks,'page_errors':errors,'business_requests':requests},ensure_ascii=False,indent=2));b.close()
