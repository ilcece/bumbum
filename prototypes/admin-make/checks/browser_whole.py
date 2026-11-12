"""通过正常UI验证整套物品挂失、准备中挂失、换新与转售的连续业务。"""
import asyncio,json,os,re
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('PROTOTYPE_URL','http://127.0.0.1:8784/preview.html')
OUT=Path(os.environ.get('PROTOTYPE_EVIDENCE','/workspace/work/admin-whole-check'));OUT.mkdir(parents=True,exist_ok=True)
async def main():
 checks=[];errors=[];requests=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000},timezone_id='Asia/Shanghai');page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append({'url':r.url,'type':r.resource_type}))
  async def button(name,root=None):await (root or page).get_by_role('button',name=re.compile(r'^(?:loading )?'+re.escape(name).replace('/',r'\/')+'$')).click()
  async def menu(name):await page.get_by_role('menuitem',name=re.compile(name+'$')).click()
  async def data():return await page.evaluate("JSON.parse(sessionStorage.getItem('bumbum-pro-prototype-v6'))")
  async def choose(label,value,root=None):
   await (root or page).get_by_label(label,exact=True).click();await page.locator('.ant-select-dropdown:visible').get_by_text(value,exact=True).click()
  async def shot(name):
   assert await page.locator('[data-private]:visible').count()==0
   await expect(page.locator('.ant-message-notice')).to_have_count(0);await page.mouse.move(300,15);await page.wait_for_timeout(350)
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await page.screenshot(path=str(OUT/(name+'.png')))
  async def configure(root):
   await button('查看密钥与配置',root);config=page.get_by_role('dialog').filter(has_text='芯片密钥、受控查看与配置核验')
   await button('〔演示〕准备密钥标记',config);await button('填入两条演示链接',config);await config.get_by_label('我已人工核对新 K0 可以认证且文件权限符合手册（演示确认）',exact=True).check();await button('〔演示〕提交双链接并确认配置核验',config);await expect(config.get_by_text('演示配置核验已记录',exact=True)).to_be_visible();await button('关闭窗口',config)
  async def finish(dialog):
   await dialog.get_by_label('实际交付核验依据',exact=True).fill('整套新实物已交付，配套芯片与接收账户逐项核对');await dialog.get_by_label('已核对整套新物品的实际交付、配套芯片和接收账户',exact=True).check();await button('确认交付并生效',dialog);await expect(dialog.get_by_text('整套新物品已生效，数字身份及发行编号沿用',exact=True)).to_be_visible()
  def ok(name):checks.append(name);print('通过：'+name,flush=True)
  try:
   await page.goto(BASE);await button('使用演示身份进入');await menu('数字物品');await button('FASH-2026-000001');drawer=page.get_by_role('dialog').filter(has_text='数字物品详情')
   await button('办理换新',drawer);work=page.get_by_role('dialog').filter(has_text='准备替换物品');await work.get_by_label('新物品实际规格',exact=True).fill('L · 黑色 · 新整套实物');await choose('新物品所配芯片','04:BB:00:00:00:00:06',work);await work.get_by_label('资格及接收对象核对依据',exact=True).fill('已核对持有人及定期换新资格');await button('保存新物品准备',work)
   work=page.get_by_role('dialog').filter(has_text='整套物品办理');await expect(work.get_by_text('原物品（实物＋芯片）',exact=True)).to_be_visible();await expect(work.get_by_text('新物品（实物＋芯片）',exact=True)).to_be_visible();await shot('whole-preparation');await configure(work);prepared=(await data())['handovers'][-1];assert prepared['kind']=='periodic';assert prepared['sourceEntityId']=='ENTITY-1-C' and prepared['entityId'];assert len((await data())['items'])==4
   await button('关闭，保留办理记录',work);await drawer.get_by_role('button',name=re.compile('关闭|Close')).first.click();await expect(drawer).not_to_be_visible();ok('从物品准备整套替换物品：原新对照、独立代次、内嵌芯片配置，准备不提前生效或增发身份')
   await page.get_by_role('button',name='原型演示 样例数据').hover();await page.get_by_role('menuitem',name=re.compile('模拟保存结果未知$')).click();await button('FASH-2026-000001');drawer=page.get_by_role('dialog').filter(has_text='数字物品详情');await button('挂失物品',drawer);loss=page.get_by_role('dialog').filter(has_text='挂失当前整套物品：实物＋芯片');await loss.get_by_label('物品挂失依据',exact=True).fill('整套实物和所配芯片一同遗失，持有人已核对');await button('确认挂失整套物品',loss)
   await expect(loss.get_by_text('保存结果未知：本次演示未写入。请核对结果后明确重试。',exact=True)).to_be_visible();await expect(loss.get_by_role('button',name=re.compile('确认挂失整套物品$'))).to_be_disabled();d=await data();assert not d['items'][0]['entities'][-1].get('lost');assert next(c for c in d['chips'] if c['id']==3)['state']=='bound'
   await button('核对保存结果',loss);await button('确认挂失整套物品',loss);await expect(loss).not_to_be_visible();d=await data();entity=d['items'][0]['entities'][-1];assert entity['lost'] and entity['lostAt'];assert d['items'][0]['ownerId']=='DEMO-B' and d['items'][0]['used']==0;assert next(c for c in d['chips'] if c['id']==3)['state']=='lost';assert d['handovers'][-1]['id']==prepared['id'] and d['handovers'][-1]['kind']=='loss';assert len(d['touches'])==27;assert sum(a['action']=='loseItem' for a in d['audits'])==1
   await drawer.get_by_text('当前整套物品已挂失',exact=True).scroll_into_view_if_needed();await shot('whole-lost-item');ok('挂失写入未知时保留输入并先核对；成功后挂失落在当代整套物品，保留身份归属额度与触碰')
   await drawer.get_by_role('button',name=re.compile('关闭|Close')).first.click();await menu('芯片管理');await button('04:BB:00:00:00:00:03');chip=page.get_by_role('dialog').filter(has_text='芯片详情');assert await chip.get_by_role('button',name=re.compile('^挂失')).count()==0;assert await chip.get_by_role('button',name='恢复当前芯片',exact=True).count()==0
   await button('〔演示〕模拟此卡触碰',chip);await expect(chip.get_by_text('当前芯片/物品不可提供有效触碰；退役、停用或候选卡不会增加次数。',exact=True)).to_be_visible();assert len((await data())['touches'])==27;ok('芯片页无独立挂失或解除入口，物品挂失后配套卡触碰被拒绝且不计次')
   await button('到物品办理挂失/换新/转售',chip);await button('继续办理换新');work=page.get_by_role('dialog').filter(has_text='挂失换新 · 整套物品办理');await expect(work.get_by_text('原整套物品已挂失，新物品尚未生效',exact=True)).to_be_visible();assert next(c for c in (await data())['chips'] if c['id']==6)['configuredAt'];ok('准备中挂失沿用原办理和已配置新物品，返回物品即可继续挂失换新')
   await page.set_viewport_size({'width':1280,'height':720});await finish(work);await expect(work.get_by_role('button',name='关闭，保留办理记录',exact=True)).to_be_in_viewport();await shot('whole-renewal-1280');await page.set_viewport_size({'width':1440,'height':1000});await work.locator('.ant-modal-body').evaluate('(e)=>e.scrollTop=0');await shot('whole-renewal-completed')
   d=await data();i=d['items'][0];assert i['entities'][-1]['id']==prepared['entityId'] and i['entities'][-1]['generation']==4;assert not i['entities'][-1].get('lost');assert i['entities'][-2]['lost'];assert i['entities'][-2]['lostAt']==entity['lostAt'];assert i['ownerId']=='DEMO-B' and i['number']==1;assert next(c for c in d['chips'] if c['id']==3)['state']=='retired';await button('关闭，保留办理记录',work);await button('〔演示〕模拟当前卡触碰');assert len((await data())['touches'])==28;ok('确认整套交付后新代正常，旧代挂失和历史保留、旧卡退役，1280按钮可达')
   await button('办理转售');work=page.get_by_role('dialog').filter(has_text='准备替换物品');await choose('转售接收账户（仅转售必填）','持有人甲 · 演示账户',work);await work.get_by_label('新物品实际规格',exact=True).fill('L · 黑色 · 转售新整套');await choose('新物品所配芯片','04:BB:00:00:00:00:07',work);await work.get_by_label('资格及接收对象核对依据',exact=True).fill('转售整套新物品与接收账户已核对');await button('保存新物品准备',work);work=page.get_by_role('dialog').filter(has_text='整套物品办理');assert (await data())['items'][0]['ownerId']=='DEMO-B';await configure(work);await finish(work);await shot('whole-resale-completed');await button('关闭，保留办理记录',work);await button('〔演示〕模拟当前卡触碰')
   d=await data();i=d['items'][0];assert i['uid']=='FASH-2026-000001' and i['number']==1 and i['ownerId']=='DEMO-A';assert i['entities'][-1]['generation']==5 and i['used']==0 and i['quotaReview'];assert len(d['items'])==4 and len(d['touches'])==29;assert next(c for c in d['chips'] if c['id']==6)['state']=='retired';ok('转售整套新物品交给新持有人，原物品退出授权，身份编号及额度延续，历代触碰累计22次')
   await page.get_by_role('button',name=re.compile('物品办理记录')).click();await page.get_by_role('row').filter(has_text='挂失换新').get_by_role('button',name='查看',exact=True).click();work=page.get_by_role('dialog').filter(has_text='挂失换新 · 整套物品办理');source=work.locator('.ant-pro-card').filter(has_text='原物品（实物＋芯片）');target=work.locator('.ant-pro-card').filter(has_text='新物品（实物＋芯片）');await expect(source.get_by_text('04:BB:00:00:00:00:03',exact=True)).to_be_visible();await expect(target.get_by_text('04:BB:00:00:00:00:06',exact=True)).to_be_visible();await expect(target.get_by_text('已替换',exact=True)).to_be_visible();await shot('whole-history-correspondence');ok('再次转售后查看旧换新记录仍对应当时两代物品，不误用当前芯片')
   assert not errors,errors;assert not [r for r in requests if r['type']!='document' and not r['url'].startswith('data:')];ok('完整整套物品主线无页面异常、无外部资源，未接真实服务')
  finally:
   (OUT/'browser-whole.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors,'base':BASE},ensure_ascii=False,indent=2));await b.close()
asyncio.run(main())
