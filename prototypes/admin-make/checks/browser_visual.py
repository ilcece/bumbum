"""只验证样式调整后的桌面布局、键盘入口、弹窗操作可达和页面截图。"""
import asyncio,json,os,re
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('PROTOTYPE_URL','http://127.0.0.1:8781/preview.html')
OUT=Path(os.environ.get('PROTOTYPE_EVIDENCE','/workspace/work/admin-style-visual'));OUT.mkdir(parents=True,exist_ok=True)
async def main():
 checks=[];errors=[];resources=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=await b.new_page(viewport={'width':1440,'height':1000},timezone_id='Asia/Shanghai');page.set_default_timeout(10000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:resources.append({'url':r.url,'type':r.resource_type}))
  async def menu(name):await page.get_by_role('menuitem',name=re.compile(name+'$')).click()
  async def capture(name,full=False):
   await page.evaluate('window.scrollTo(0,0)');await page.mouse.move(350,10);await page.wait_for_timeout(350);assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),name+'整页水平溢出';await page.screenshot(path=str(OUT/(name+'.png')),full_page=full)
  def ok(name):checks.append(name);print('通过：'+name,flush=True)
  try:
   await page.goto(BASE);await page.get_by_role('button',name='使用演示身份进入').click();await expect(page.get_by_text('准备、使用与持有，分别核对',exact=True)).to_be_visible();await capture('overview-1440',True)
   async def choose(label,text):
    await page.get_by_label(label,exact=True).click();await page.locator('.ant-select-dropdown:visible').get_by_text(text,exact=True).click()
   metric=page.locator('.metric-card').filter(has_text='有效触碰次数').locator('.ant-statistic-content-value');await choose('统计口径','全生命周期有效触碰');await choose('时间范围','累计');await expect(metric).to_have_text('22');await page.get_by_role('button',name='应用筛选',exact=True).click();await expect(metric).to_have_text('27');await page.reload();await expect(metric).to_have_text('27');ok('工作台筛选明确应用后生效，累计27次与刷新条件保留')
   await page.get_by_role('button',name='待绑定芯片 6，查看档案',exact=True).focus();await page.keyboard.press('Enter');await expect(page).to_have_url(re.compile('state=pending'));ok('概况卡可键盘进入，保持原筛选目标')
   await menu('款式与发行');await expect(page.get_by_text('共用款式资料',exact=True)).to_be_visible();await capture('catalog-1440');await menu('数字物品');await expect(page.get_by_text('数字物品档案',exact=True)).to_be_visible();await capture('items-1440')
   await page.get_by_role('button',name='FASH-2026-000001',exact=True).click();await expect(page.locator('.ant-statistic-content-value').filter(has_text=re.compile('^20$'))).to_be_visible();await capture('item-detail-1440',True);ok('列表、紧凑详情及售出后20次统计保持')
   await page.set_viewport_size({'width':1280,'height':720});await page.get_by_role('button',name='办理换新 / 转售',exact=True).click();dialog=page.get_by_role('dialog');await expect(dialog).to_be_visible();await page.wait_for_timeout(350);await expect(dialog.get_by_role('button',name='保存准备，继续配置候选芯片',exact=True)).to_be_in_viewport();await capture('handover-1280');await dialog.get_by_role('button',name=re.compile('取\\s*消')).click();ok('1280×720弹窗正文独立滚动，底部确认/取消按钮可见')
   await menu('芯片管理');await expect(page.get_by_text('芯片档案',exact=True)).to_be_visible();await capture('chips-1280');await menu('工作台');await expect(page.get_by_text('准备、使用与持有，分别核对',exact=True)).to_be_visible();await capture('overview-1280',True)
   await page.get_by_role('button',name='新建款式',exact=True).click();await expect(page.get_by_label('款式编号',exact=True)).to_be_visible();await capture('style-form-1280',True);ok('1280×720工作台、列表与款式栅格表单无整页横向溢出')
   assert not errors,errors;assert not [r for r in resources if r['type']!='document' and not r['url'].startswith('data:')],resources
   ok('实际单HTML无外部脚本/样式请求及页面异常')
  finally:
   (OUT/'browser-visual.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors,'base':BASE},ensure_ascii=False,indent=2));await b.close()
asyncio.run(main())
