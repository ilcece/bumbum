"""核对关键保存异常、离开保护、统计切换与列表上下文。"""
import asyncio,json,os,re
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('PROTOTYPE_URL','http://127.0.0.1:8765/')
OUT=Path(os.environ.get('PROTOTYPE_EVIDENCE','/workspace/work/umi-recovery'));OUT.mkdir(parents=True,exist_ok=True)
async def main():
 checks=[];errors=[]
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  page=await b.new_page(viewport={'width':1280,'height':720},timezone_id='Asia/Shanghai');page.set_default_timeout(10000);page.on('pageerror',lambda e:errors.append(str(e)))
  async def click(s,root=None):await (root or page).get_by_role('button',name=re.compile(re.escape(s))).click()
  async def menu(s):await page.get_by_role('menuitem',name=re.compile(s+'$')).click()
  async def demo(s):await page.get_by_role('button',name='原型演示 样例数据').hover();await page.get_by_role('menuitem',name=re.compile(s+'$')).click()
  def ok(s):checks.append(s);print('通过：'+s,flush=True)
  try:
   await page.goto(BASE);await click('使用演示身份进入');await click('新建款式');await page.get_by_label('款式编号',exact=True).fill('RECOVERY');await page.get_by_label('款式名称',exact=True).fill('输入保留测试')
   await menu('数字物品');dialog=page.get_by_role('dialog');await expect(dialog).to_be_visible();await click('继续编辑',dialog);await expect(page.get_by_label('款式名称',exact=True)).to_have_value('输入保留测试');ok('离开未保存表单可继续编辑，输入保留')
   await demo('模拟保存失败');await click('保存共用资料');await expect(page.get_by_text('模拟保存失败：输入及原记录保留。',exact=True)).to_be_visible();await expect(page.get_by_label('款式名称',exact=True)).to_have_value('输入保留测试');ok('保存失败保留原输入，不创建新记录')
   await demo('模拟保存结果未知');await click('保存共用资料');await expect(page.get_by_text('保存结果未知：本次演示未写入。请核对结果后明确重试。',exact=True)).to_be_visible();await expect(page.get_by_role('button',name=re.compile('保存共用资料$'))).to_be_disabled();await click('核对保存结果');await click('保存共用资料');await expect(page).to_have_url(re.compile(r'/catalog/style/(?!new)'));ok('未知保存先核对，禁止盲目重复提交，明确重试仅创建一次')
   await page.get_by_label('款式名称',exact=True).fill('保存后离开测试');await menu('数字物品');await click('保存后继续',page.get_by_role('dialog'));await expect(page.get_by_text('数字物品档案',exact=True)).to_be_visible();ok('保存后继续完成实际保存与导航')
   await menu('工作台');await click('新建款式');await page.get_by_label('款式编号',exact=True).fill('DISCARD');await menu('工作台');await click('放弃并继续',page.get_by_role('dialog'));await expect(page.get_by_text('准备、使用与持有，分别核对',exact=True)).to_be_visible();ok('放弃并继续不创建记录')
   await demo('模拟读取失败');await expect(page.get_by_text('读取失败，已保存记录仍保留',exact=True)).to_be_visible();await click('重试读取');await expect(page.get_by_text('有效触碰次数',exact=True)).to_be_visible();ok('读取失败独立反馈，重试保留已有档案')
   await click('FASH-2026-000001');await expect(page.locator('.ant-statistic-content-value').filter(has_text=re.compile('^20$'))).to_be_visible();await page.get_by_label('统计对象',exact=True).click();await page.locator('.ant-select-dropdown:visible').get_by_text('全生命周期有效触碰',exact=True).click();await expect(page.locator('.ant-statistic-content-value').filter(has_text=re.compile('^25$'))).to_be_visible();await page.screenshot(path=str(OUT/'lifetime-1280.png'),full_page=True);ok('物品同一身份售后20/生命周期25切换，逐芯片明细保留')
   await menu('芯片管理');await page.get_by_label('关键词',exact=True).fill('DEMO-002');await click('查 询');await expect(page).to_have_url(re.compile('keyword=DEMO-002'));await click('04:BB:00:00:00:00:11');await click('返回来源');await expect(page.get_by_label('关键词',exact=True)).to_have_value('DEMO-002');await page.reload();await expect(page.get_by_label('关键词',exact=True)).to_have_value('DEMO-002');ok('已提交筛选、详情来源返回及刷新保留')
   await menu('款式与发行');await page.get_by_role('tab',name='发行约定',exact=True).click();await page.get_by_label('关键词',exact=True).fill('限时');await click('查 询');await page.reload();await expect(page.get_by_role('tab',name='发行约定',exact=True)).to_have_attribute('aria-selected','true');await expect(page.get_by_label('关键词',exact=True)).to_have_value('限时');ok('发行页签内查询与刷新保留当前页签及条件');await menu('芯片管理')
   await click('手工登记芯片');dialog=page.get_by_role('dialog');await dialog.get_by_label('芯片UID',exact=True).fill('04:AA:BB:CC:DD:EE:01');await dialog.get_by_label('批次（选填）',exact=True).fill('RECOVERY-BATCH');await click('登记并查看',dialog);await expect(page.get_by_text('RECOVERY-BATCH',exact=True)).to_be_visible();await click('返回来源');await click('手工登记芯片');dialog=page.get_by_role('dialog');await dialog.get_by_label('芯片UID',exact=True).fill('04:AA:BB:CC:DD:EE:01');await click('登记并查看',dialog);await expect(dialog.get_by_text('芯片已登记，不新增或覆盖原批次。',exact=True)).to_be_visible();ok('连续手工登记定位确切UID，重复登记不覆盖既有来源和批次')
   assert not errors,errors
  finally:
   await page.screenshot(path=str(OUT/'last.png'),full_page=True);(OUT/'browser-recovery.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors,'base':BASE},ensure_ascii=False,indent=2));print('LAST_URL',page.url,flush=True);print('ERRORS',errors,flush=True);await b.close()
asyncio.run(main())
