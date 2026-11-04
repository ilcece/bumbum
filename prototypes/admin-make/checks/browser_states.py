"""定向验证原型的保存异常、图片、连续创建与查询上下文，不涉及组件矩阵。"""
import base64,json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
URL=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8644'
OUT=Path(sys.argv[2] if len(sys.argv)>2 else '/workspace/artifacts/admin-interactive-prototype');OUT.mkdir(parents=True,exist_ok=True)
results=[];errors=[]
def passed(name):results.append({'case':name,'status':'passed'});print('通过：'+name,flush=True)
def data(page):
 d=page.evaluate("JSON.parse(sessionStorage.getItem('bumbum-make-prototype-v5'))")
 for i in d['items']:
  style=next((s for s in d['styles'] if s['id']==i['styleId']),None)
  i['profile']=style['profile'] if style else None
 for m in d['identities'].values():
  issue=next((s for s in d['issuances'] if s['id']==m['issuanceId']),None)
  m['edition']=f"#{m['editionNumber']:03d}"+(f"/{issue['total']}" if issue['total'] is not None else "") if issue and m['editionNumber'] else None
 return d
def save_shared(page,m):
 m.get_by_role('button',name='保存共用资料',exact=True).click()
 modal(page).get_by_role('button',name='确认同步保存',exact=True).click()
 page.wait_for_timeout(450)
def modal(page):return page.locator('.ant-modal:visible').last
def menu(page,name):page.get_by_role('menuitem',name=re.compile(name)).click()
def detail(page):menu(page,'物品管理');page.get_by_role('button',name='FASH-2026-000002',exact=True).click()
def edit(page):page.locator('.ant-drawer:visible').get_by_role('button',name='维护共用资料',exact=True).click();return modal(page)
def close_detail(page):page.locator('.ant-drawer:visible .ant-drawer-close').click()
def mode(page,label):page.get_by_role('button',name='原型演示 · 样例数据',exact=True).click();page.get_by_role('menuitem',name=label,exact=True).click()
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1600,'height':1000});page.set_default_timeout(7000);page.on('pageerror',lambda e:errors.append(str(e)))
 try:
  page.goto(URL,wait_until='networkidle');page.get_by_role('button',name='使用演示身份进入').click();mode(page,'保存失败');detail(page);m=edit(page);m.get_by_label('名称',exact=True).fill('失败后保留的样例名称');save_shared(page,m);expect(m.get_by_text(re.compile('模拟保存失败'))).to_be_visible();expect(m.get_by_label('名称',exact=True)).to_have_value('失败后保留的样例名称');assert data(page)['items'][1]['profile']['name']!='失败后保留的样例名称';passed('保存失败保留输入且不改原资料')
  m.get_by_role('button',name='恢复正常演示').click();save_shared(page,m);expect(page.locator('.ant-modal:visible')).to_have_count(0);assert data(page)['items'][1]['profile']['name']=='失败后保留的样例名称';passed('失败恢复后明确重试保存成功');close_detail(page)
  mode(page,'保存结果未知');detail(page);m=edit(page);m.get_by_label('名称',exact=True).fill('未知结果样例名称');save_shared(page,m);expect(m.get_by_role('button',name='核对保存结果')).to_be_visible();expect(m.get_by_role('button',name='保存共用资料',exact=True)).to_be_disabled();assert data(page)['items'][1]['profile']['name']!='未知结果样例名称';m.get_by_role('button',name='核对保存结果').click();m.get_by_role('button',name='恢复正常演示').click();save_shared(page,m);expect(page.locator('.ant-modal:visible')).to_have_count(0);passed('未知结果先核对，不自动重发或误报成功')
  m=edit(page);before=len(data(page)['items'][1]['profile']['image_urls']);m.locator('input[type=file]').set_input_files({'name':'sample.png','mimeType':'image/png','buffer':base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==')});expect(m.locator('.ant-upload-list-item-done')).to_have_count(before+1);assert len(data(page)['items'][1]['profile']['image_urls'])==before;passed('Upload选择与预览仅暂存，未保存不关联');page.screenshot(path=str(OUT/'item-edit.png'));save_shared(page,m);expect(page.locator('.ant-modal:visible')).to_have_count(0);assert len(data(page)['items'][1]['profile']['image_urls'])==before+1;passed('图片保存到共用资料，同步物品引用');close_detail(page)
  page.get_by_role('button',name=re.compile('创建物品草稿$')).click();m=modal(page);uid=m.get_by_placeholder('FASH-2026-000007');uid.fill('FASH-2026-999001');m.get_by_role('combobox').click();page.locator('.ant-select-dropdown:visible .ant-select-item-option').first.click();uid.fill('FASH-2026-999001');m.get_by_role('button',name='创建并继续',exact=True).click();expect(uid).to_have_value('');assert any(i['item_uid']=='FASH-2026-999001' for i in data(page)['items']);passed('连续创建保留类别引用并清空已提交字段');uid.fill('FASH-2026-999001');count=len(data(page)['items']);m.get_by_role('button',name='创建并继续',exact=True).click();assert len(data(page)['items'])==count;passed('重复物品编号拒绝覆盖')
  m.get_by_role('button',name=re.compile(r'^取\s*消$')).click();modal(page).get_by_role('button',name='确认关闭',exact=True).click()
  search=page.get_by_placeholder('搜索物品编号、款式、名称或芯片 UID',exact=True);print('查询placeholder',search.get_attribute('placeholder'),flush=True);search.fill('FASH-2026-000002');search.press('Enter');expect(page.get_by_role('button',name='FASH-2026-000002',exact=True)).to_be_visible();page.get_by_role('button',name='FASH-2026-000002',exact=True).click();close_detail(page);expect(search).to_have_value('FASH-2026-000002');page.reload(wait_until='networkidle');page.get_by_role('button',name='使用演示身份进入').click();expect(page.get_by_placeholder('搜索物品编号、款式、名称或芯片 UID',exact=True)).to_have_value('FASH-2026-000002');passed('已生效查询返回及刷新后仍保留')
  assert not errors,errors;passed('异常与图片路径无页面运行错误')
 except Exception as exc:
  page.screenshot(path=str(OUT/'states-failure.png'));results.append({'case':'当前路径','status':'failed','error':str(exc)});raise
 finally:
  (OUT/'browser-states.json').write_text(json.dumps({'results':results,'page_errors':errors},ensure_ascii=False,indent=2));b.close()
