"""只验证隔离交互原型的业务路径，不运行React独立组件冒烟或调用真实后台。"""
import base64,json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
URL=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8644'
OUT=Path(sys.argv[2] if len(sys.argv)>2 else '/workspace/artifacts/admin-interactive-prototype');OUT.mkdir(parents=True,exist_ok=True)
results=[];errors=[];business_requests=[]
def record(name):results.append({'case':name,'status':'passed'});print('通过：'+name,flush=True)
def snapshot(page,name):page.screenshot(path=str(OUT/(name+'.png')))
def data(page):
 d=page.evaluate("JSON.parse(sessionStorage.getItem('bumbum-make-prototype-v3'))")
 for i in d['items']:
  style=next((s for s in d['styles'] if s['id']==i['styleId']),None)
  i['profile']=style['profile'] if style else None
 for m in d['identities'].values():
  issue=next((s for s in d['issuances'] if s['id']==m['issuanceId']),None)
  m['edition']=f"#{m['editionNumber']:03d}/{issue['total']}" if issue and m['editionNumber'] else None
 return d
def save_shared(page,m):
 m.get_by_role('button',name='保存共用资料',exact=True).click()
 modal(page).get_by_role('button',name='确认同步保存',exact=True).click()
 page.wait_for_timeout(450)
def modal(page):return page.locator('.ant-modal:visible').last
def menu(page,name):page.get_by_role('menuitem',name=re.compile(name)).click()
def item(page,uid):menu(page,'物品管理');page.get_by_role('button',name=uid,exact=True).click();expect(page.get_by_role('button',name='申请换新',exact=True)).to_be_visible()
def select(page,label,text):page.get_by_label(label,exact=True).click();page.locator('.ant-select-dropdown:visible').get_by_text(text,exact=True).last.click();expect(page.locator('.ant-select-dropdown:visible')).to_have_count(0)
def enter(page):page.goto(URL,wait_until='networkidle');page.get_by_role('button',name='使用演示身份进入').click();expect(page.get_by_role('menuitem',name='工作台总览')).to_be_visible()
def workflow(page,kind):
 uid='FASH-2026-000001' if kind=='resale' else 'FASH-2026-000002'
 item(page,uid);page.get_by_role('button',name='办理转售' if kind=='resale' else '申请换新',exact=True).click()
 if kind=='resale':select(page,'接收人','持有人乙 · 演示账户')
 if kind!='resale':select(page,'目标尺码','L')
 page.get_by_label('申请与资格核对记录',exact=True).fill('原型样例：已核对申请来源和接收对象')
 page.get_by_role('button',name='保存申请，进入准备',exact=True).click();expect(page.get_by_label('候选新芯片',exact=True)).to_be_visible()
 d=data(page);work=d['works'][0];old_item=next(i for i in d['items'] if i['id']==work['itemId']);old_id=old_item['bound_chip_id'];old_owner=d['identities'][str(work['itemId'])]['ownerId'];used=d['identities'][str(work['itemId'])]['used']
 if kind=='resale':
  expect(page.get_by_label('目标尺码',exact=True)).to_have_count(0);select(page,'本次交付尺码','L')
 page.get_by_label('候选新芯片',exact=True).click();page.locator('.ant-select-dropdown:visible .ant-select-item-option:visible').first.click()
 page.get_by_role('button',name='〔演示〕填入样例核验引用').click();page.get_by_role('button',name='记录准备完成，进入交付',exact=True).click();expect(page.get_by_label('发货记录',exact=True)).to_be_visible()
 d=data(page);w=d['works'][0];assert next(i for i in d['items'] if i['id']==w['itemId'])['bound_chip_id']==old_id
 assert next(c for c in d['chips'] if c['id']==w['candidateChipId'])['item_id'] is None
 record(kind+'：准备不激活新芯片')
 page.get_by_label('发货记录',exact=True).fill('原型样例发货，未填写真实地址');page.get_by_role('button',name='记录发货',exact=True).click()
 expect(page.get_by_role('button',name='记录收到新实体',exact=True)).to_be_visible();d=data(page);assert next(i for i in d['items'] if i['id']==w['itemId'])['bound_chip_id']==old_id
 record(kind+'：发货不切换授权或归属')
 page.get_by_role('button',name='记录收到新实体',exact=True).click();page.locator('.ant-modal-confirm:visible').last.get_by_role('button',name='记录收到',exact=True).click();expect(page.get_by_label('交付核验记录',exact=True)).to_be_visible()
 d=data(page);assert d['identities'][str(w['itemId'])]['ownerId']==old_owner
 record(kind+'：收到后仍等待正式接续')
 page.get_by_label('交付核验记录',exact=True).fill('原型样例：已核对实际收到新实体与接收对象');page.get_by_role('checkbox',name='已核对实际交付、接收对象与新旧实体').check()
 snapshot(page,kind+'-handover')
 page.get_by_role('button',name=re.compile('确认正式接续$')).click();page.locator('.ant-modal-confirm:visible').last.get_by_role('button',name=re.compile('确认正式接续$')).click();expect(page.get_by_text('正式接续已完成',exact=True)).to_be_visible()
 d=data(page);w=d['works'][0];meta=d['identities'][str(w['itemId'])];updated=next(i for i in d['items'] if i['id']==w['itemId']);assert next(c for c in d['chips'] if c['id']==old_id)['chip_status']=='retired';assert updated['bound_chip_id']==w['candidateChipId']
 assert len([e for e in meta['entities'] if not e.get('exitedAt')])==1;assert meta['entities'][-1]['size']=='L';assert meta['entities'][-1]['color']=='黑色';assert meta['edition']==('#001/100' if kind=='resale' else '#002/100')
 assert meta['ownerId']==('DEMO-OWNER-B' if kind=='resale' else old_owner)
 if kind=='resale':assert meta['used']==used and len(meta['ownership'])==2
 else:assert meta['quotaReview'] is True and len(meta['ownership'])==1
 record(kind+'：正式接续保持编号、唯一当前实体与正确归属/历史')
 page.get_by_role('button',name='查看物品及历史',exact=True).click();expect(page.get_by_text('当前实体与历史实体',exact=True)).to_be_visible()
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1600,'height':1000});page.set_default_timeout(7000)
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:business_requests.append(r.url) if '/api/' in r.url else None)
 try:
  page.goto(URL,wait_until='networkidle');snapshot(page,'login');page.get_by_role('button',name=re.compile(r'^登\s*录$')).click();expect(page.get_by_text('请输入管理员账号和密码。',exact=True)).to_be_visible();record('演示登录空输入反馈')
  page.get_by_role('button',name='使用演示身份进入').click();snapshot(page,'overview');record('演示登录与原稿工作台导航')
  item(page,'FASH-2026-000001');expect(page.get_by_role('button',name='申请换新',exact=True)).to_be_disabled();record('已用年度额度禁用再次换新')
  expect(page.get_by_text('当前实体与历史实体',exact=True)).to_be_visible();expect(page.get_by_text('所有权流转记录',exact=True)).to_be_visible();snapshot(page,'item-detail');record('详情三层信息与独立历史分区')
  page.get_by_role('button',name='维护共用资料',exact=True).last.click();edit=modal(page);edit.get_by_label('名称',exact=True).fill('尚未保存的测试名称');edit.get_by_role('button',name=re.compile(r'^取\s*消$')).click();modal(page).get_by_role('button',name='放弃并继续',exact=True).click();assert data(page)['items'][0]['profile']['name']!='尚未保存的测试名称';record('取消编辑保留原资料')
  page.get_by_role('button',name='维护共用资料',exact=True).last.click();edit=modal(page);edit.get_by_label('名称',exact=True).fill('原型已保存的限定T恤');save_shared(page,edit);expect(page.locator('.ant-drawer:visible').get_by_text('原型已保存的限定T恤',exact=True).first).to_be_visible();assert data(page)['items'][1]['profile']['name']=='原型已保存的限定T恤';record('保存共用资料同步同款引用物品')
  page.get_by_text('查看共用资料',exact=True).click();expect(modal(page).get_by_text('款式与发行约定',exact=True)).to_be_visible();snapshot(page,'issuance');modal(page).get_by_role('button',name=re.compile(r'^关\s*闭$')).last.click();record('共用发行资料引用与只读实际实体快照')
  page.locator('.ant-drawer:visible .ant-drawer-close').click()
  workflow(page,'periodic');page.locator('.ant-drawer:visible .ant-drawer-close').click()
  workflow(page,'resale');page.locator('.ant-drawer:visible').get_by_role('button',name='挂失芯片',exact=True).click();modal(page).locator('textarea').fill('原型挂失申请及核对记录');modal(page).get_by_role('button',name='确认挂失',exact=True).click();expect(page.locator('.ant-drawer:visible').get_by_text('已挂失',exact=True).last).to_be_visible();assert data(page)['identities']['1']['used']==1;record('挂失阻断当前芯片且不扣换新次数')
  page.locator('.ant-drawer:visible .ant-drawer-close').click();menu(page,'芯片管理');page.get_by_role('button',name=re.compile('手工登记芯片$')).click();record('手工登记入口可达')
  registration=modal(page);before=len(data(page)['chips']);registration.get_by_placeholder('如 04:A2:7F:1B:5E:80:18 或 04a27f1b5e8018').fill('04:AA:BB:CC:DD:EE:77');registration.get_by_placeholder('选填，如 HZ-202610-F03').fill('DEMO-BATCH');registration.get_by_role('button',name='登记并继续下一枚',exact=True).click();assert len(data(page)['chips'])==before+1;expect(registration.get_by_placeholder('选填，如 HZ-202610-F03')).to_have_value('');record('连续登记成功后清空UID/批次，无项目录入')
  registration.get_by_placeholder('如 04:A2:7F:1B:5E:80:18 或 04a27f1b5e8018').fill('04:AA:BB:CC:DD:EE:77');registration.get_by_placeholder('选填，如 HZ-202610-F03').fill('不得覆盖原批次');registration.get_by_role('button',name='登记并继续下一枚',exact=True).click();d=data(page);assert len(d['chips'])==before+1;assert next(c for c in d['chips'] if c['chip_uid']=='04:AA:BB:CC:DD:EE:77')['batch_no']=='DEMO-BATCH';record('重复登记不新增且不覆盖原记录')
  modal(page).get_by_role('button',name=re.compile(r'^取\s*消$')).click();menu(page,'操作日志');expect(page.get_by_text('保存商品资料',exact=True).first).to_be_visible();record('原型操作日志反映已保存动作')
  assert not errors,errors;assert not business_requests,business_requests;record('无页面运行异常且未请求真实业务API')
 except Exception as exc:
  snapshot(page,'review-failure');results.append({'case':'当前路径','status':'failed','error':str(exc)});raise
 finally:
  (OUT/'browser-review.json').write_text(json.dumps({'results':results,'page_errors':errors,'business_requests':business_requests},ensure_ascii=False,indent=2));b.close()
