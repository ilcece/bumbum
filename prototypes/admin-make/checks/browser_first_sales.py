"""验证三类商品共用首交界面；配卡前置使用显式合成夹具，真实链路另测。"""
import json,re,sys,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
url=sys.argv[1];out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
results=[];errors=[];requests=[]
def passed(name):
 results.append({'case':name,'status':'passed'});print('通过：'+name,flush=True)
def raw(p):return p.evaluate("JSON.parse(sessionStorage.getItem('bumbum-make-prototype-v5'))")
def dialog(p):return p.locator('.ant-modal:visible').last
def select(p,field,label):
 field.click();p.locator('.ant-select-dropdown:visible').get_by_text(label,exact=True).last.click()
def login(p):
 p.goto(url,wait_until='networkidle');p.get_by_role('button',name='使用演示身份进入').click();p.get_by_role('menuitem',name=re.compile('物品管理')).click();p.get_by_role('tab',name='办理记录',exact=True).click()
def create(p,name,line='1',piece='1'):
 p.get_by_role('button',name='登记订单件次',exact=True).first.click();e=dialog(p)
 select(p,e.get_by_label('销售计划',exact=True),name+' · 首次销售')
 e.get_by_label('外部订单引用',exact=True).fill('DEMO-MIXED-ORDER')
 e.get_by_label('订单明细引用',exact=True).fill(line);e.get_by_label('本明细第几件',exact=True).fill(piece)
 e.get_by_label('订单要求规格',exact=True).fill({'紫檀手串':'腕围17cm，珠径8mm','T恤':'L码／白色','棒球帽':'帽围56–60cm／蓝色'}[name])
 e.get_by_label('收件安排引用',exact=True).fill('礼赠收件安排B（演示）')
 e.get_by_role('button',name='保存订单件次',exact=True).click();return dialog(p)
def shot(p,name):p.wait_for_timeout(200);p.screenshot(path=str(out/name),animations='disabled')
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);p=b.new_page(viewport={'width':1600,'height':1000});p.set_default_timeout(9000)
 p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:requests.append(r.url) if '/api/' in r.url else None)
 try:
  login(p);before=raw(p);p.get_by_role('button',name='〔演示〕添加三类销售样例',exact=True).click();expect(p.get_by_role('row').filter(has_text='紫檀手串 · 首次销售')).to_be_visible()
  data=raw(p);assert len(data['salesPlans'])==3 and len(data['items'])==len(before['items']) and len(data['chips'])==len(before['chips'])
  assert [s['quantity'] for s in data['salesPlans']]==[50,100,20]
  passed('三类销售样例共用计划结构，计划数不自动生成身份/芯片或改变发行上限');shot(p,'first-sales-plans.png')
  # 准备已登记、配置的合成前置记录；不声称该设置本身验证了配卡页面。
  for n,(plan,prefix) in enumerate(zip(data['salesPlans'],['JEW','FASH','FASH'])):
   item_id=910001+n;chip_id=920001+n;issue_id='TEST-FIRST-ISSUE-'+str(n)
   issue={'id':issue_id,'name':'仅用于浏览器验证的发行约定'+str(n),'styleId':plan['styleId'],'rightIds':[],'total':50 if n==0 else None,'description':'合成夹具：T恤/帽子实际发行口径待业务决定','status':'issued'}
   data['issuances'].append(issue)
   template=dict(data['items'][0]);template.update(id=item_id,styleId=plan['styleId'],item_uid=f'{prefix}-2026-{item_id:06}',status='draft',owner_status='unclaimed',owner_account_id=None,bound_chip_id=chip_id,bound_chip_uid=f'04:11:22:33:44:55:{n+1:02}',bound_chip_status='bound',bound_chip_keys_generated=True,bound_chip_provisioned_at='2026-11-05T01:00:00Z')
   data['items'].append(template)
   chip=dict(data['chips'][0]);chip.update(id=chip_id,item_id=item_id,chip_uid=template['bound_chip_uid'],chip_status='bound',keys_generated=True,provisioned_at='2026-11-05T01:00:00Z');data['chips'].append(chip)
   data['identities'][str(item_id)]={'issuanceId':issue_id,'editionNumber':1,'ownerId':None,'firstOwnerAt':None,'used':0,'entities':[],'ownership':[]}
  p.evaluate('(d)=>sessionStorage.setItem("bumbum-make-prototype-v5",JSON.stringify(d))',data);login(p)
  for n,name in enumerate(['紫檀手串','T恤','棒球帽']):
   e=create(p,name,str(n+1));e.get_by_label('投产核对依据',exact=True).fill('人工核对样例：付款、规格、有效订单及名额均已查验')
   e.get_by_role('button',name='保存投产核对',exact=True).click();expect(e.get_by_label('工厂接单确认',exact=True)).to_be_visible()
   e.get_by_label('工厂接单确认',exact=True).fill('工厂已确认清单 DEMO-PROD-'+str(n))
   e.get_by_label('工厂来货引用',exact=True).fill('工厂寄给品牌 DEMO-INBOUND-'+str(n));e.get_by_role('button',name='保存工厂接单与来货',exact=True).click()
   e.get_by_label('实际实体规格',exact=True).fill({'紫檀手串':'腕围17cm／8mm','T恤':'L码／白色','棒球帽':'帽围56–60cm／蓝色'}[name])
   select(p,e.get_by_label('实体质量结果',exact=True),'合格');e.get_by_label('验收依据',exact=True).fill('与封样一致，外观及规格通过')
   e.get_by_role('button',name='保存验收结果',exact=True).click();expect(e.get_by_label('对应数字物品',exact=True)).to_be_visible()
   if n==0:
    e.get_by_role('button',name='登记数字物品',exact=True).click();expect(p.get_by_role('tab',name='数字物品',exact=True)).to_have_attribute('aria-selected','true')
    p.get_by_role('tab',name='办理记录',exact=True).click();p.get_by_role('row').filter(has_text='DEMO-MIXED-ORDER / 1 / 第1件').get_by_role('button',name='继续首交',exact=True).click();e=dialog(p)
    expect(e.get_by_label('对应数字物品',exact=True)).to_be_visible();passed('配卡阶段可进入既有数字物品工作区，返回继续同一首交且阶段保留')
   prefix='JEW' if n==0 else 'FASH';select(p,e.get_by_label('对应数字物品',exact=True),f'{prefix}-2026-{910001+n} · #001'+('/50' if n==0 else ''))
   e.get_by_label('出厂检查依据',exact=True).fill('合成前置：关联与配置记录一致，商品资料正确')
   e.get_by_role('button',name='保存出厂检查',exact=True).click();expect(e.get_by_text('请逐项核对实体、规格/编号、芯片和用户资料。',exact=True)).to_be_visible()
   for label in ['实体质量已通过','订单规格与发行编号对应','关联芯片及配置核验对应','用户商品资料正确']:e.get_by_role('checkbox',name=label,exact=True).check()
   if n==0:shot(p,'first-sales-packing.png')
   e.get_by_role('button',name='保存出厂检查',exact=True).click();expect(e.get_by_label('品牌发货引用',exact=True)).to_be_visible()
   e.get_by_label('品牌发货引用',exact=True).fill('品牌寄给顾客 DEMO-OUTBOUND-'+str(n));e.get_by_role('button',name='记录品牌发货',exact=True).click()
   saved=raw(p)['firstDeliveries'][0];assert saved['stage']==5
   assert raw(p)['identities'][str(910001+n)]['ownerId'] is None
   e.get_by_label('实际交付依据',exact=True).fill('人工核对实际收货及礼赠安排，仅记录物流事实');e.get_by_role('button',name='记录实际交付',exact=True).click()
   expect(e.get_by_text('实物交付事实已记录',exact=True)).to_be_visible();assert raw(p)['firstDeliveries'][0]['stage']==6
   identity=raw(p)['identities'][str(910001+n)];assert identity['ownerId'] is None and identity['used']==0 and identity['entities']==[]
   assert next(i for i in raw(p)['items'] if i['id']==910001+n)['status']=='draft'
   if n==2:shot(p,'first-sales-delivered.png')
   e.get_by_role('button',name='返回并保留已保存进度',exact=True).click()
   passed(name+'：共用首交六阶段及检查阻断通过；发货/实际交付不启用、不认领、不扣权益')
  assert len({r['orderRef'] for r in raw(p)['firstDeliveries']})==1 and len({r['itemId'] for r in raw(p)['firstDeliveries']})==3
  passed('同一混合订单的三条明细分别对应三件数字身份和芯片')
  e=create(p,'紫檀手串','1');expect(e.get_by_text('该店铺订单明细的件次已登记，请查询原记录，不能重复派产。',exact=True)).to_be_visible();assert len(raw(p)['firstDeliveries'])==3
  e.get_by_role('button',name=re.compile(r'^取\s*消$')).click();dialog(p).get_by_role('button',name='放弃修改',exact=True).click();passed('重复店铺订单明细件次被拒绝，未新增生产/首交记录')
  e=create(p,'棒球帽','4');e.get_by_label('投产核对依据',exact=True).fill('人工核对');e.get_by_role('button',name='保存投产核对',exact=True).click()
  e.get_by_label('工厂接单确认',exact=True).fill('接单依据');e.get_by_label('工厂来货引用',exact=True).fill('来货依据');e.get_by_role('button',name='保存工厂接单与来货',exact=True).click()
  e.get_by_label('实际实体规格',exact=True).fill('帽围不符');select(p,e.get_by_label('实体质量结果',exact=True),'不合格，暂停交付');e.get_by_label('验收依据',exact=True).fill('与样品不符，返工')
  e.get_by_role('button',name='保存验收结果',exact=True).click();expect(e.get_by_text('异常暂停',exact=True)).to_be_visible();assert raw(p)['firstDeliveries'][0]['stage']==2
  expect(e.get_by_role('button',name='保存出厂检查',exact=True)).to_have_count(0);shot(p,'first-sales-quality-hold.png')
  e.get_by_role('button',name='返回并保留已保存进度',exact=True).click();passed('不合格到货暂停在验收，不能配卡或发货；记录保留')
  p.get_by_role('button',name='原型演示 · 样例数据',exact=True).click();p.get_by_role('menuitem',name='保存结果未知',exact=True).click()
  e=create(p,'T恤','5');expect(e.get_by_role('button',name='保存订单件次',exact=True)).to_be_disabled();assert len(raw(p)['firstDeliveries'])==4
  expect(e.get_by_role('button',name='核对保存结果',exact=True)).to_be_visible();e.get_by_role('button',name='核对保存结果',exact=True).click();e.get_by_role('button',name='保存订单件次',exact=True).click();expect(dialog(p).get_by_label('投产核对依据',exact=True)).to_be_visible()
  passed('未知回执不写入或自动重发，核对后明确重试且输入保留')
  dialog(p).get_by_role('button',name='返回并保留已保存进度',exact=True).click();previous=raw(p);login(p);assert raw(p)['firstDeliveries']==previous['firstDeliveries'];passed('刷新保留首交事实和异常，不重置旧v5样例')
  p.get_by_text('换新与转售',exact=True).click();expect(p.get_by_label('办理类型',exact=True)).to_be_visible();passed('原换新/转售查询入口保留')
  p.set_viewport_size({'width':1280,'height':720});p.get_by_text('首次销售与交付',exact=True).click();p.get_by_role('row').filter(has_text='DEMO-MIXED-ORDER').first.get_by_role('button',name='继续首交',exact=True).click();expect(dialog(p).get_by_role('button',name='保存投产核对',exact=True)).to_be_visible();shot(p,'first-sales-small-window.png');passed('1280×720办理弹窗操作栏可达')
  assert not errors,errors;assert not requests,requests;passed('无页面运行异常或真实业务接口请求')
 except Exception as exc:
  results.append({'case':'当前路径','status':'failed','error':str(exc)});shot(p,'first-sales-failure.png');raise
 finally:
  (out/'browser-first-sales.json').write_text(json.dumps({'results':results,'page_errors':errors,'business_requests':requests,'fixture_scope':'配卡前置为明确注入的合成身份/芯片，已有建档配卡UI另用browser_chip_demo验证'},ensure_ascii=False,indent=2));b.close()
