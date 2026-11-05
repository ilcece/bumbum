"""通过正常界面验证固定/非限定共用发售流程及失败恢复，不预置业务数据。"""
import json,re,sys,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
url=sys.argv[1];out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True);results=[];errors=[]
def ok(case):results.append({'case':case,'status':'passed'});print('通过：'+case,flush=True)
def raw():return p.evaluate("JSON.parse(sessionStorage.getItem('bumbum-make-prototype-v5'))")
def m():return p.locator('.ant-modal:visible').last
def select(field,text):field.scroll_into_view_if_needed();p.wait_for_timeout(350);field.click();p.locator('.ant-select-dropdown:visible').get_by_text(text,exact=True).last.click()
def mode(text):p.get_by_role('button',name='原型演示 · 样例数据',exact=True).click();p.get_by_role('menuitem',name=text,exact=True).click()
def register(count,order,state='已核对有效'):
 p.get_by_role('button',name='登记订单件次',exact=True).click();m().get_by_label('网店商品',exact=True).click();p.locator('.ant-select-dropdown:visible .ant-select-item-option').first.click()
 m().get_by_label('本次登记件数（同一明细逐件展开）',exact=True).fill(str(count));select(m().get_by_label('销售有效性核对',exact=True),state)
 for label,value in [('订单范围及付款核对依据','合成付款核对'),('外部订单引用',order),('订单明细引用','LINE'),('订单要求规格','按封样规格'),('收件安排引用','合成安排')]:m().get_by_label(label,exact=True).fill(value)
 m().get_by_role('button',name='保存订单件次',exact=True).click()
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);p=b.new_page(viewport={'width':1280,'height':720});p.set_default_timeout(7000);p.on('pageerror',lambda e:errors.append(str(e)))
 try:
  p.goto(url,wait_until='networkidle');p.get_by_role('button',name='使用演示身份进入',exact=True).click()
  for kind,label,forecast in [('fixed','固定总量',50),('unlimited','非限定',100)]:
   p.get_by_role('menuitem',name=re.compile('工作台')).click();p.get_by_role('button',name='新建发售',exact=True).click();p.get_by_label('商品款式',exact=True).click();p.locator('.ant-select-dropdown:visible .ant-select-item-option').first.click();p.get_by_role('button',name='商品已准备，继续发行设置',exact=True).click()
   p.get_by_label('本次发售名称',exact=True).fill(label+'通用流程');select(p.get_by_label('发行方式',exact=True),label);p.get_by_label('预估销售件数（备料参考）',exact=True).fill(str(forecast))
   if kind=='fixed':p.get_by_label('固定发行总量',exact=True).fill('50')
   for field,value in [('对外发行承诺与规格约定',label+'，按封样规格'),('有效售出与退款核定口径','合成付款及退款核对口径'),('交期与交付安排','按需生产'),('工厂供货依据引用','合成供货协议'),('封样与验收标准引用','合成封样')]:p.get_by_label(field,exact=True).fill(value)
   if kind=='fixed':
    mode('保存结果未知');p.get_by_role('button',name='保存发售草稿并继续',exact=True).click();expect(p.get_by_role('button',name='保存发售草稿并继续',exact=True)).to_be_disabled();assert not raw()['salesPlans'];p.get_by_role('button',name='核对保存结果',exact=True).click();expect(p.get_by_label('本次发售名称',exact=True)).to_have_value(label+'通用流程');ok('发售未知结果不写入或自动重发，核对后输入保留')
   p.get_by_role('button',name='保存发售草稿并继续',exact=True).click()
   if kind=='fixed':
    p.get_by_role('button',name='返回发售列表',exact=True).click();p.get_by_role('tab',name='发行档案',exact=True).click();row=p.get_by_role('row').filter(has_text=label+'通用流程');expect(row.get_by_role('button',name=re.compile(r'^删\s*除$'))).to_be_disabled();row.get_by_role('button',name='进入本次发售',exact=True).click()
   else:p.get_by_role('button',name='核对商品与发行',exact=True).click()
   p.get_by_role('button',name='确认规则，继续渠道上架',exact=True).click();sale=raw()['salesPlans'][-1];issue=next(i for i in raw()['issuances'] if i['id']==sale['issuanceId']);assert issue['total']==(50 if kind=='fixed' else None);assert len(raw()['items'])==18;ok(label+'通过相同发售工作区确认，不自动生成物品或芯片')
   p.get_by_role('button',name='添加网店商品',exact=True).click();m().get_by_label('平台与店铺',exact=True).fill('测试店'+kind);m().get_by_label('网店商品引用',exact=True).fill('SKU-'+kind);m().get_by_role('button',name='保存网店商品',exact=True).click();p.get_by_role('button',name='登记已上架',exact=True).click();p.get_by_role('button',name='各店已上架，开始销售',exact=True).click();p.get_by_role('tab',name='订单与交付',exact=True).click()
   if kind=='fixed':
    register(51,'OVER-51');expect(m().get_by_text('有效销售件数将超过固定发行上限，请核对或登记为待核对，不增发身份。',exact=True)).to_be_visible();assert not raw()['firstDeliveries'];m().get_by_label('本次登记件数（同一明细逐件展开）',exact=True).fill('50');m().get_by_role('button',name='保存订单件次',exact=True).click();m().get_by_role('button',name='返回并保留已保存进度',exact=True).click();register(1,'REVIEW-1','付款/退款/跨期等待核对');select(m().get_by_label('销售核对结论',exact=True),'核对有效');m().get_by_label('投产核对依据',exact=True).fill('测试超额不能改有效');m().get_by_role('button',name='保存投产核对',exact=True).click();expect(m().get_by_text('有效销售件数将超过固定发行上限，请核对或保持待核，不增发身份。',exact=True)).to_be_visible();m().get_by_role('button',name='返回并保留已保存进度',exact=True).click();m().get_by_role('button',name='放弃修改',exact=True).click();ok('固定50拒绝51件有效销售，超额待核也不能经投产改为有效')
   else:
    register(101,'UNLIMITED-101');m().get_by_role('button',name='返回并保留已保存进度',exact=True).click();assert len([r for r in raw()['firstDeliveries'] if r['planId']==sale['id']])==101;ok('非限定预估100仍可登记101件，不生成固定分母')
   p.get_by_role('tab',name='概览',exact=True).click();
   if kind=='fixed':expect(p.get_by_text(re.compile(r'待生产 50 .*异常 1'))).to_be_visible()
   expect(p.get_by_text('本次发售的使用情况',exact=True)).to_be_visible();p.screenshot(path=str(out/(kind+'-overview-1280.png')),animations='disabled')
  p.get_by_role('menuitem',name=re.compile('商品与发售')).click();p.get_by_role('button',name='返回发售列表',exact=True).click();p.get_by_role('tab',name='商品款式',exact=True).click();p.reload(wait_until='networkidle');p.get_by_role('button',name='使用演示身份进入',exact=True).click();expect(p.get_by_role('tab',name='商品款式',exact=True)).to_have_attribute('aria-selected','true');p.goto(url+'?legacy=1#items?view=styles',wait_until='networkidle');p.get_by_role('button',name='使用演示身份进入',exact=True).click();expect(p.get_by_role('tab',name='商品款式',exact=True)).to_have_attribute('aria-selected','true');assert not errors,errors;ok('旧款式链接指向新位置；1280×720概览可用，商品款式页签刷新保持，无页面错误')
 except Exception as exc:
  p.screenshot(path=str(out/'modes-failure.png'));results.append({'case':'当前路径','status':'failed','error':str(exc)});raise
 finally:
  (out/'browser-sale-modes.json').write_text(json.dumps({'results':results,'page_errors':errors},ensure_ascii=False,indent=2));b.close()
