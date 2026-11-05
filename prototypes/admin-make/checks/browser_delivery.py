"""检查最终单HTML的所有一级页面及资源请求，并留存干净截图。"""
import asyncio,json,re,os
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('PROTOTYPE_URL','http://127.0.0.1:8766/preview.html')
OUT=Path(os.environ.get('PROTOTYPE_EVIDENCE','/workspace/work/umi-delivery-check'));OUT.mkdir(parents=True,exist_ok=True)
async def main():
 errors=[];resources=[]
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1280,'height':720},timezone_id='Asia/Shanghai');page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:resources.append({'url':r.url,'type':r.resource_type}))
  await page.goto(BASE);await page.get_by_role('button',name='使用演示身份进入').click()
  for menu in ['工作台','款式与发行','数字物品','芯片管理','系统管理']:
   await page.get_by_role('menuitem',name=re.compile(menu+'$')).click();await expect(page.get_by_text({'工作台':'物品与芯片概况','款式与发行':'共用款式资料','数字物品':'数字物品档案','芯片管理':'芯片档案','系统管理':'本地演示操作记录'}[menu],exact=True)).to_be_visible()
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),menu+'整页水平溢出'
  await page.get_by_role('tab',name='连接与范围',exact=True).click();await expect(page.get_by_text('未连接',exact=True)).to_be_visible()
  await page.get_by_role('menuitem',name=re.compile('工作台$')).click();await page.get_by_role('button',name='FASH-2026-000001',exact=True).click();await page.mouse.move(300,10);await page.evaluate('window.scrollTo(0,0)');await page.wait_for_timeout(800);await page.screenshot(path=str(OUT/'item-20.png'),full_page=True)
  await page.get_by_role('button',name='办理换新 / 转售',exact=True).click();await expect(page.get_by_role('dialog')).to_be_visible();await page.wait_for_timeout(400);await page.screenshot(path=str(OUT/'handover-1280.png'))
  assert not errors,errors
  extra=[r for r in resources if r['type']!='document' and not r['url'].startswith('data:')]
  assert not extra,extra
  (OUT/'browser-delivery.json').write_text(json.dumps({'passed':True,'routes':5,'viewport':'1280x720','errors':errors,'externalResources':extra,'documentRequests':[r['url'] for r in resources if r['type']=='document'],'fileNavigation':'ERR_BLOCKED_BY_ADMINISTRATOR；同一个HTML通过本机HTTP验证'},ensure_ascii=False,indent=2));print('通过：五个主页面、1280宽度、未接入状态、零外部资源及截图')
  await b.close()
asyncio.run(main())
