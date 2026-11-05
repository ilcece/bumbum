"""从空白界面连续完成限时发售、多店销售、滚动交付及137件封版；不注入身份。"""
import json,re,sys,shutil
from pathlib import Path
from datetime import datetime,timedelta,timezone
from playwright.sync_api import sync_playwright,expect
url=sys.argv[1];out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True);results=[];errors=[];requests=[]
def ok(name):results.append({'case':name,'status':'passed'});print('通过：'+name,flush=True)
def raw():return p.evaluate("JSON.parse(sessionStorage.getItem('bumbum-make-prototype-v5'))")
def modal():return p.locator('.ant-modal:visible').last
def select(field,label):
 field.click();p.locator('.ant-select-dropdown:visible').get_by_text(label,exact=True).last.click()
def shot(name):p.wait_for_timeout(400);p.screenshot(path=str(out/name),animations='disabled')
def record_order(channel,order,count):
 p.get_by_role('button',name='登记订单件次',exact=True).click();m=modal();select(m.get_by_label('网店商品',exact=True),channel)
 m.get_by_label('本次登记件数（同一明细逐件展开）',exact=True).fill(str(count));m.get_by_label('达到付款条件时间（北京时间）',exact=True).fill(paid)
 m.get_by_label('订单范围及付款核对依据',exact=True).fill('合成外部订单清单，已核对有效付款与件数')
 m.get_by_label('外部订单引用',exact=True).fill(order);m.get_by_label('订单明细引用',exact=True).fill('LINE-1')
 m.get_by_label('订单要求规格',exact=True).fill('帽围56–60cm，蓝色');m.get_by_label('收件安排引用',exact=True).fill('合成收件安排A')
 m.get_by_role('button',name='保存订单件次',exact=True).click();return modal()
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);p=b.new_page(viewport={'width':1600,'height':1000});p.set_default_timeout(7000)
 p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:requests.append(r.url) if '/api/' in r.url else None)
 try:
  p.goto(url,wait_until='networkidle');p.get_by_role('button',name='使用演示身份进入',exact=True).click();assert p.get_by_role('menuitem').count()==5
  expect(p.get_by_text('有效触碰统计',exact=True)).to_be_visible();expect(p.get_by_text('经营工作台',exact=True)).to_be_visible();shot('01-business-and-statistics.png');ok('5个业务入口及经营/库存/触碰统计共同保留')
  p.get_by_role('button',name='新建发售',exact=True).click();p.get_by_role('button',name='新建商品款式',exact=True).click();m=modal()
  m.get_by_label('款式编号',exact=True).fill('JOURNEY-CAP-NEW');m.get_by_label('名称',exact=True).fill('全流程限时棒球帽');m.get_by_label('介绍',exact=True).fill('多店销售一个月后按核定销量确定发行总量');m.get_by_role('button',name='保存共用资料',exact=True).click();expect(p.get_by_role('dialog',name='新建共用款式商品资料',exact=True)).to_be_hidden()
  p.get_by_role('button',name='商品已准备，继续发行设置',exact=True).click();p.get_by_label('本次发售名称',exact=True).fill('帽子一个月限时发售')
  bj=datetime.now(timezone(timedelta(hours=8)));paid=bj.strftime('%Y-%m-%dT%H:%M')
  p.get_by_label('销售开始时间（北京时间）',exact=True).fill((bj-timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'));p.get_by_label('销售结束时间（北京时间）',exact=True).fill((bj+timedelta(days=29)).strftime('%Y-%m-%dT%H:%M'))
  p.get_by_label('对外发行承诺与规格约定',exact=True).fill('限时按有效销量定量；预估100，不设100硬上限，允许滚动交付')
  p.get_by_label('有效售出与退款核定口径',exact=True).fill('窗口内有效付款，核定时已完成取消/退款的排除，待核事项先解决')
  p.get_by_label('交期与交付安排',exact=True).fill('按需生产，合格后滚动交付');p.get_by_label('工厂供货依据引用',exact=True).fill('合成供货协议A');p.get_by_label('封样与验收标准引用',exact=True).fill('合成封样A')
  shot('02-preparation-flow.png');p.get_by_role('button',name='保存发售草稿并继续',exact=True).click();expect(p.get_by_role('tab',name='概览',exact=True)).to_have_attribute('aria-selected','true')
  sale=raw()['salesPlans'][-1];assert sale['quantity']==100 and sale['mode']=='timed';assert next(i for i in raw()['issuances'] if i['id']==sale['issuanceId'])['total'] is None;ok('从新建发售连续新建款式和限时规则，100为预估，未预建单件或芯片')
  p.get_by_role('button',name='核对商品与发行',exact=True).click();p.get_by_role('button',name='确认规则，继续渠道上架',exact=True).click();expect(p.get_by_role('tab',name='销售与封版',exact=True)).to_have_attribute('aria-selected','true')
  for shop,product in [('网店A','CAP-A'),('网店B','CAP-B')]:
   p.get_by_role('button',name='添加网店商品',exact=True).click();m=modal();m.get_by_label('平台与店铺',exact=True).fill(shop);m.get_by_label('网店商品引用',exact=True).fill(product);m.get_by_role('button',name='保存网店商品',exact=True).click();expect(p.get_by_role('dialog',name='添加网店商品',exact=True)).to_be_hidden()
   p.get_by_role('row').filter(has_text=shop).get_by_role('button',name='登记已上架',exact=True).click()
  p.get_by_role('button',name='各店已上架，开始销售',exact=True).click();expect(p.get_by_text('销售中',exact=True).first).to_be_visible();ok('规则确认与多店商品上架衔接，确认规则未提前锁定总量')
  p.get_by_role('tab',name='订单与交付',exact=True).click();record_order('网店A / CAP-A','ORDER-A',80);expect(modal().get_by_label('投产核对依据',exact=True)).to_be_visible();modal().get_by_role('button',name='返回并保留已保存进度',exact=True).click()
  record_order('网店B / CAP-B','ORDER-A',57);expect(modal().get_by_label('投产核对依据',exact=True)).to_be_visible();modal().get_by_role('button',name='返回并保留已保存进度',exact=True).click();assert len(raw()['firstDeliveries'])==137
  ok('两个网店同订单号分别登记80和57件，共137件，第101件不被预估100阻断')
  record_order('网店A / CAP-A','ORDER-A',1);expect(modal().get_by_text('该店铺订单明细的件次已登记，请查询原记录。',exact=True)).to_be_visible();assert len(raw()['firstDeliveries'])==137;modal().get_by_role('button',name=re.compile(r'^取\s*消$')).click();modal().get_by_role('button',name='放弃修改',exact=True).click();ok('同店铺重复件次阻断，不同店铺同单号保留独立事实')
  # A店首件先完成交付，其余订单仍留待处理，验证销售和履约并行。
  target=next(r for r in raw()['firstDeliveries'] if r['piece']==1 and r['channelId']==raw()['salesPlans'][-1]['channels'][0]['id']);p.get_by_label('首次交付查询',exact=True).fill(target['id']);p.get_by_role('button',name='继续首交',exact=True).click();m=modal();m.get_by_label('投产核对依据',exact=True).fill('合成订单已核对，明确规格及供货可投产');m.get_by_role('button',name='保存投产核对',exact=True).click();expect(m.get_by_label('工厂接单确认',exact=True)).to_be_visible()
  m.get_by_role('button',name='记录异常并暂停',exact=True).click();e=modal();e.get_by_label('异常说明',exact=True).fill('这段草稿必须取消');e.get_by_role('button',name=re.compile(r'^取\s*消$')).click();m.get_by_role('button',name='记录异常并暂停',exact=True).click();e=modal();expect(e.get_by_label('异常说明',exact=True)).to_have_value('');e.get_by_role('button',name='保存异常',exact=True).click();expect(p.get_by_text('请填写当前核对依据',exact=True)).to_be_visible();assert not next(r for r in raw()['firstDeliveries'] if r['id']==target['id']).get('exception');e.get_by_role('button',name=re.compile(r'^取\s*消$')).click();ok('取消的异常草稿不会残留或在空白确认时静默提交')
  m.get_by_label('工厂接单确认',exact=True).fill('工厂已接单，稍后寄出');m.get_by_role('button',name='保存工厂接单',exact=True).click();assert next(r for r in raw()['firstDeliveries'] if r['id']==target['id'])['stage']==1;assert next(r for r in raw()['firstDeliveries'] if r['id']==target['id'])['factoryRef'];ok('工厂尚未寄货时可独立保存接单，进度不被来货字段阻断')
  m.get_by_label('工厂来货引用（未寄出时可留空）',exact=True).fill('工厂寄给品牌INBOUND-A');m.get_by_role('button',name='记录来货，进入验收',exact=True).click();expect(m.get_by_label('实际实体规格',exact=True)).to_be_visible()
  m.get_by_label('实际实体规格',exact=True).fill('帽围不符，54cm');select(m.get_by_label('实体质量结果',exact=True),'不合格，暂停交付');m.get_by_label('验收依据',exact=True).fill('第一次验收：与封样不符');m.get_by_role('button',name='保存验收结果',exact=True).click();m.get_by_role('button',name='核对后继续',exact=True).click();e=modal();e.get_by_label('异常处理依据',exact=True).fill('返工后重新到货，准备复验');e.get_by_role('button',name='记录核对依据并继续',exact=True).click();m=modal();m.get_by_label('实际实体规格',exact=True).fill('帽围56–60cm，蓝色');select(m.get_by_label('实体质量结果',exact=True),'合格');m.get_by_label('验收依据',exact=True).fill('第二次复验通过');m.get_by_role('button',name='保存验收结果',exact=True).click();expect(m.get_by_role('button',name='为本件建档并关联',exact=True)).to_be_visible();assert len(next(r for r in raw()['firstDeliveries'] if r['id']==target['id'])['qualityAttempts'])==2;ok('返工复验后保留两轮规格、结果及依据，不覆盖旧验收事实')
  m.get_by_role('button',name='为本件建档并关联',exact=True).click();target=next(r for r in raw()['firstDeliveries'] if r['id']==target['id']);assert target['itemId'];item=next(i for i in raw()['items'] if i['id']==target['itemId']);uid=item['item_uid'];assert raw()['identities'][str(item['id'])]['editionNumber'] is None
  m.get_by_role('button',name='芯片登记与配卡',exact=True).click();expect(p.get_by_role('button',name='返回本次交付',exact=True)).to_be_visible();p.get_by_role('button',name='〔演示〕触发Webhook登记',exact=True).click();p.get_by_role('button',name=re.compile('立即绑定物品$')).click();m=modal();expect(m.get_by_placeholder('搜索物品编号、款式编号或名称')).to_have_value(uid);m.get_by_role('radio',name='选择物品 '+uid,exact=True).check();m.get_by_role('checkbox').check();m.get_by_role('button',name='确认首次绑定',exact=True).click();p.get_by_role('button',name=re.compile('继续生成密钥与配卡核验$')).click();m=modal();m.get_by_role('button',name='〔演示〕生成芯片密钥标记',exact=True).click();m.get_by_role('checkbox',name=re.compile('我确认查看密钥')).check();m.get_by_role('button',name='〔演示〕查看密钥占位与模板',exact=True).click();m.get_by_role('button',name='〔演示〕填入两条递增链接',exact=True).click();m.get_by_role('checkbox',name=re.compile('我已人工核对新 K0')).check();m.get_by_role('button',name='〔演示〕提交双链接核验样例',exact=True).click();expect(m.get_by_text('〔演示〕配置核验通过样例已记录；未校验真实卡片或凭证。',exact=True)).to_be_visible();m.get_by_role('button',name='关闭窗口',exact=True).click();p.get_by_role('button',name='返回本次交付',exact=True).click();expect(modal().get_by_label('对应数字物品',exact=True)).to_be_visible();ok('从当前件次建档进入配卡，自动定位目标并返回同一发售/同一交付，不靠记编号重选')
  m=modal();m.get_by_label('出厂检查依据',exact=True).fill('核对实物/规格编号、关联芯片配置及商品资料');m.get_by_role('button',name='保存出厂检查',exact=True).click();expect(m.get_by_text('请逐项核对实体、规格/编号、芯片和用户资料。',exact=True)).to_be_visible()
  for label in ['实体质量已通过','订单规格与发行编号对应','关联芯片及配置核验对应','用户商品资料正确']:m.get_by_role('checkbox',name=label,exact=True).check()
  m.get_by_role('button',name='保存出厂检查',exact=True).click();m.get_by_label('品牌发货引用',exact=True).fill('品牌寄给顾客OUTBOUND-A');m.get_by_role('button',name='记录品牌发货',exact=True).click();m.get_by_label('实际交付依据',exact=True).fill('合成实际收货，未推定所有权');m.get_by_role('button',name='记录实际交付',exact=True).click();expect(m.get_by_text('实物交付事实已记录',exact=True)).to_be_visible();shot('03-rolling-delivery.png');m.get_by_role('button',name='返回并保留已保存进度',exact=True).click();ok('销售期内完成一件交付，其余136件继续履约；不自动认领或消耗权益')
  p.get_by_role('tab',name='销售与封版',exact=True).click();p.get_by_role('button',name='〔演示〕将业务时间推进到销售期满',exact=True).click()
  for shop in ['网店A','网店B']:p.get_by_role('row').filter(has_text=shop).get_by_role('button',name='登记已停售',exact=True).click()
  p.get_by_role('button',name='各店已停售，进入对账',exact=True).click();expect(p.get_by_role('button',name='预览并确认封版',exact=True)).to_be_disabled();ok('各店未核对完成时不能封版，销售结束不冒充履约完成')
  for shop,count in [('网店A',80),('网店B',57)]:
   p.get_by_role('row').filter(has_text=shop).get_by_role('button',name='核对网店销售',exact=True).click();m=modal();m.get_by_label('网店核定有效件数',exact=True).fill(str(count+1));m.get_by_label('订单范围、退款及来源核对依据',exact=True).fill('故意核对差异');m.get_by_role('button',name='确认该店核对完成',exact=True).click();expect(m.get_by_text('网店核定件数与已登记有效件数不一致，请补单或核对差异。',exact=True)).to_be_visible();m.get_by_label('网店核定有效件数',exact=True).fill(str(count));m.get_by_label('订单范围、退款及来源核对依据',exact=True).fill(shop+'合成对账范围，付款与退款核对完毕');m.get_by_role('button',name='确认该店核对完成',exact=True).click();expect(p.get_by_role('dialog',name='核对网店有效销售',exact=True)).to_be_hidden()
  p.get_by_role('button',name='预览并确认封版',exact=True).click();m=modal();m.get_by_label('最终数量核定依据',exact=True).fill('两店80+57，合计137件；已核对来源与异常');m.get_by_role('checkbox').check();shot('04-seal-137-preview.png');m.get_by_role('button',name='确认最终发行结果',exact=True).click();expect(p.get_by_role('dialog',name='预览并确认发售封版',exact=True)).to_be_hidden();sealed=raw()['salesPlans'][-1];assert sealed['finalCount']==137;assert next(i for i in raw()['issuances'] if i['id']==sale['issuanceId'])['total']==137;assert raw()['identities'][str(item['id'])]['editionNumber']==1;assert len(raw()['items'])==19;ok('各店核定数量不一致阻断，核清后预估100最终137，正式编号封版确定，稳定身份不变且不批量虚造137个物品')
  shot('05-sealed-result.png');p.reload(wait_until='networkidle');p.get_by_role('button',name='使用演示身份进入',exact=True).click();assert raw()['salesPlans'][-1]['finalCount']==137;expect(p.get_by_role('tab',name='销售与封版',exact=True)).to_have_attribute('aria-selected','true');ok('刷新保留发售、页签、销售结果和单件关联')
  p.get_by_role('tab',name='订单与交付',exact=True).click();expect(p.get_by_role('button',name='登记订单件次',exact=True)).to_be_disabled();p.get_by_role('menuitem',name=re.compile('交付与售后')).click();p.get_by_role('tab',name='换新与转售',exact=True).click();p.reload(wait_until='networkidle');p.get_by_role('button',name='使用演示身份进入',exact=True).click();expect(p.get_by_role('tab',name='换新与转售',exact=True)).to_have_attribute('aria-selected','true');p.get_by_role('menuitem',name=re.compile('工作台')).click();expect(p.get_by_text('有效触碰统计',exact=True)).to_be_visible();assert not errors,errors;assert not requests,requests;ok('封版后不普通追加订单；原统计继续可用，无页面异常或真实业务API请求')
 except Exception as exc:
  shot('journey-failure.png');results.append({'case':'当前连续路径','status':'failed','error':str(exc)});print(p.locator('body').inner_text()[-7000:],flush=True);raise
 finally:
  (out/'browser-sale-journey.json').write_text(json.dumps({'results':results,'page_errors':errors,'business_requests':requests,'scope':'从空白UI建款/发行/多店订单/身份/芯片并交付，再按137件封版；仅内置密钥/Webhook等演示控件，无存储写入注入。'},ensure_ascii=False,indent=2));b.close()
