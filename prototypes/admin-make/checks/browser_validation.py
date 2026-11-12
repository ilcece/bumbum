"""通过正常页面验证900px抽屉、发行编号展示与生产验证对象的直接删除。"""
import asyncio,json,os,re
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('PROTOTYPE_URL','http://127.0.0.1:8783/preview.html')
OUT=Path(os.environ.get('PROTOTYPE_EVIDENCE','/workspace/work/admin-validation-check'));OUT.mkdir(parents=True,exist_ok=True)
async def main():
 checks=[];errors=[];resources=[]
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=await browser.new_page(viewport={'width':1440,'height':1000},timezone_id='Asia/Shanghai');page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:resources.append({'url':r.url,'type':r.resource_type}))
  async def button(name,root=None):await (root or page).get_by_role('button',name=name,exact=True).click()
  async def menu(name):await page.get_by_role('menuitem',name=re.compile(name+'$')).click()
  async def data():return await page.evaluate("JSON.parse(sessionStorage.getItem('bumbum-pro-prototype-v6'))")
  async def shot(name):
   assert await page.locator('[data-private]:visible').count()==0
   await page.locator('.ant-drawer-body').evaluate_all('(els)=>els.forEach(e=>e.scrollTop=0)');await expect(page.locator('.ant-message-notice')).to_have_count(0)
   await page.mouse.move(350,10);await page.wait_for_timeout(350);await page.screenshot(path=str(OUT/(name+'.png')))
  async def close(drawer):await drawer.get_by_role('button',name=re.compile('关闭|Close')).first.click();await expect(drawer).not_to_be_visible()
  def ok(name):checks.append(name);print('通过：'+name,flush=True)
  try:
   await page.goto(BASE);await button('使用演示身份进入');await menu('数字物品');await button('FASH-2026-000001');drawer=page.get_by_role('dialog').filter(has_text='数字物品详情');await expect(drawer).to_be_visible();await page.wait_for_function("document.querySelector('.ant-drawer-content-wrapper')?.getBoundingClientRect().width===900")
   edition=drawer.get_by_text('#001/100',exact=True);await expect(edition).to_be_visible();assert await edition.locator('..').locator('.ant-typography-copy').count()==0;assert await drawer.get_by_role('button',name='复制 FASH-2026-000001',exact=True).count()>=1
   await expect(drawer.get_by_role('button',name='直接删除验证物品',exact=True)).to_have_count(0);await drawer.get_by_role('switch',name='物品生产验证对象',exact=True).click();await expect(drawer.get_by_role('switch',name='物品生产验证对象',exact=True)).to_be_checked();await expect(drawer.get_by_role('button',name='直接删除验证物品',exact=True)).to_be_visible();d=await data();assert d['items'][0]['isValidation'] and not next(c for c in d['chips'] if c['id']==3).get('isValidation');assert len(d['touches'])==27
   await shot('validation-item-900');ok('物品抽屉900px，发行编号无复制且物品编号仍可复制；开关独立不改变触碰记录')
   await drawer.get_by_role('switch',name='物品生产验证对象',exact=True).click();await expect(drawer.get_by_role('button',name='直接删除验证物品',exact=True)).to_have_count(0);await drawer.get_by_role('switch',name='物品生产验证对象',exact=True).click();await close(drawer);await expect(page.get_by_text('生产验证对象',exact=True)).to_be_visible();await page.reload();await button('FASH-2026-000001');drawer=page.get_by_role('dialog').filter(has_text='数字物品详情');await expect(drawer.get_by_role('switch',name='物品生产验证对象',exact=True)).to_be_checked();await close(drawer);ok('标记可开关、列表显示，刷新保持；未标记时没有直接删除按钮')
   await menu('芯片管理');await button('04:BB:00:00:00:00:03');drawer=page.get_by_role('dialog').filter(has_text='芯片详情');await page.wait_for_function("document.querySelector('.ant-drawer-content-wrapper')?.getBoundingClientRect().width===900");await drawer.get_by_role('switch',name='芯片生产验证对象',exact=True).click();await shot('validation-chip-900');await page.set_viewport_size({'width':1280,'height':720});await expect(drawer.get_by_role('button',name='直接删除验证芯片',exact=True)).to_be_visible();assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await shot('validation-chip-1280');await button('直接删除验证芯片',drawer);await expect(drawer).not_to_be_visible();assert await page.get_by_role('dialog').count()==0
   d=await data();i=next(i for i in d['items'] if i['id']==1);assert i['ownerId']=='DEMO-B' and i['number']==1 and i['sold'];assert not any(c['id']==3 for c in d['chips']);assert not any(e['chipId']==3 for e in d['touches']);assert len(i['entities'])==2;assert len(d['chips'])==10;ok('已绑定已配置的验证芯片一键删除，无资格弹窗；物品、持有人、发行及其他芯片保留')
   await menu('数字物品');await button('FASH-2026-000001');drawer=page.get_by_role('dialog').filter(has_text='数字物品详情');await expect(drawer.get_by_role('switch',name='物品生产验证对象',exact=True)).to_be_checked();await button('直接删除验证物品',drawer);await expect(drawer).not_to_be_visible();d=await data();assert not any(i['id']==1 for i in d['items']);assert not any(e['itemId']==1 for e in d['touches']);assert not any(c['itemId']==1 for c in d['chips']);assert len(d['chips'])==10;assert next(i for i in d['items'] if i['id']==2)['uid']=='FASH-2026-000002';assert sum(a['action']=='deleteValidation' for a in d['audits'])==2;ok('已售出已认领有历史的验证物品直接删除，关联清理且另一侧档案/操作审计保留')
   await menu('芯片管理');await button('手工登记芯片');dialog=page.get_by_role('dialog');await dialog.get_by_label('芯片UID',exact=True).fill('04:AA:BB:CC:DD:EE:88');await dialog.get_by_label('生产验证对象',exact=True).click();await button('登记并查看',dialog);await expect(page.get_by_role('switch',name='芯片生产验证对象',exact=True)).to_be_checked();d=await data();c=next(c for c in d['chips'] if c['uid']=='04:AA:BB:CC:DD:EE:88');assert c['isValidation'];await button('直接删除验证芯片');await expect(page).to_have_url(re.compile(r'#/chips'));ok('登记芯片可直接标生产验证，完整详情删除后返回来源')
   await menu('数字物品');await button('登记数字物品');dialog=page.get_by_role('dialog');await dialog.get_by_label('关联发行约定',exact=True).click();await page.locator('.ant-select-dropdown:visible').get_by_text('经典T恤 · 首次发行 · 限定100个身份',exact=True).click();await dialog.get_by_label('生产验证对象',exact=True).click();await button('登记并查看物品',dialog);await expect(page.get_by_role('switch',name='物品生产验证对象',exact=True)).to_be_checked();await button('直接删除验证物品');await expect(page).to_have_url(re.compile(r'#/items'));ok('登记物品可标生产验证，草稿无额外条件直接删除')
   await menu('系统管理');await expect(page.get_by_text('删除生产验证对象',exact=True).first).to_be_visible();assert not errors,errors;assert not [r for r in resources if r['type']!='document' and not r['url'].startswith('data:')];ok('操作审计可见，单HTML无页面异常或外部资源')
  finally:
   (OUT/'browser-validation.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors,'base':BASE},ensure_ascii=False,indent=2));await browser.close()
asyncio.run(main())
