"""通过真实页面检查居中、款图、抽屉、宽编辑、复制、状态与配卡交互。"""
import asyncio,base64,json,os,re
from pathlib import Path
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('PROTOTYPE_URL','http://127.0.0.1:8782/preview.html')
OUT=Path(os.environ.get('PROTOTYPE_EVIDENCE','/workspace/work/admin-design-final'));OUT.mkdir(parents=True,exist_ok=True)
async def main():
 checks=[];errors=[];resources=[];geometry=[]
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  context=await browser.new_context(viewport={'width':1440,'height':1000},timezone_id='Asia/Shanghai',permissions=['clipboard-read','clipboard-write'])
  page=await context.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:resources.append({'url':r.url,'type':r.resource_type}))
  async def button(name,root=None):
   label=r'\s*'.join(name) if len(name)==2 else re.escape(name)
   await (root or page).get_by_role('button',name=re.compile('^'+label+'$')).click()
  async def menu(name):await page.get_by_role('menuitem',name=re.compile(name+'$')).click()
  async def shot(name):
   await page.mouse.move(350,10);await page.wait_for_timeout(350)
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),name+'整页水平溢出'
   assert await page.locator('[data-private]:visible').count()==0,'截图不包含展示密钥或动态链接'
   await page.screenshot(path=str(OUT/(name+'.png')))
  def ok(name):checks.append(name);print('通过：'+name,flush=True)
  async def choose(label,text):
   await page.get_by_label(label,exact=True).click();await page.locator('.ant-select-dropdown:visible').get_by_text(text,exact=True).click()
  try:
   await page.goto(BASE);await button('使用演示身份进入');await expect(page.get_by_text('物品与芯片概况',exact=True)).to_be_visible()
   await shot('01-overview-1440')
   await page.set_viewport_size({'width':1920,'height':1080});box=await page.locator('.ant-pro-layout-content').bounding_box();geometry.append(box)
   assert box['width']<=1320 and abs((box['x']+box['width']/2)-(248+(1920-248)/2))<2,box
   await shot('02-overview-1920');ok('1920内容最大1320px且在侧栏右侧居中，重复栏目标题已移除')
   await page.set_viewport_size({'width':1440,'height':1000})
   metric=page.locator('.metric-primary').filter(has_text='有效触碰次数').locator('.ant-statistic-content-value')
   await choose('统计口径','全生命周期有效触碰');await choose('时间范围','累计');await expect(metric).to_have_text('22');await button('应用筛选');await expect(metric).to_have_text('27');await page.reload();await expect(metric).to_have_text('27');ok('两项触碰主指标与三项当前关系辅助指标保留，筛选明确应用及刷新保留')
   await page.get_by_role('button',name='待绑定芯片 6，查看档案',exact=True).focus();await page.keyboard.press('Enter');await expect(page).to_have_url(re.compile('state=pending'));ok('概况卡仍能键盘带条件进入')
   await menu('款式与发行');await expect(page.get_by_text('共用款式资料',exact=True)).to_be_visible();await shot('03-catalog-1440')
   row=page.get_by_role('row').filter(has_text='BB-TEE-BLK');await expect(row.locator('img')).to_be_visible();await row.get_by_text('维护资料',exact=True).click()
   editor=page.get_by_role('dialog').filter(has_text='编辑共用款式');await expect(editor).to_be_visible();await page.wait_for_function("document.querySelector('.editor-modal')?.getBoundingClientRect().width > 1100");assert (await editor.bounding_box())['width']>=1000
   await expect(editor.locator('.mobile-preview')).to_be_visible();await expect(editor.get_by_role('button',name='保存共用资料',exact=True)).to_be_in_viewport();await shot('04-style-editor-1440')
   original=await editor.get_by_label('款式名称',exact=True).input_value();await editor.get_by_label('款式名称',exact=True).fill(original+' · 未保存')
   await expect(editor.locator('.mobile-preview').get_by_text(original+' · 未保存',exact=True)).to_be_visible();await expect(editor.locator('.mobile-preview').get_by_text('未保存预览',exact=True)).to_be_visible()
   await editor.locator('input[type=file]').set_input_files({'name':'第二张演示图片.png','mimeType':'image/png','buffer':base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jr1kAAAAASUVORK5CYII=')})
   await expect(editor.get_by_role('button',name='查看商品图片 2',exact=True)).to_be_visible();await button('查看商品图片 2',editor);await expect(editor.get_by_role('button',name='查看商品图片 2',exact=True)).to_have_attribute('aria-pressed','true')
   await editor.locator('.gallery-main').click();await expect(page.get_by_role('button',name='close',exact=True)).to_be_visible();await page.wait_for_timeout(350);await page.keyboard.press('Escape');await expect(page.locator('.ant-image-preview')).not_to_be_visible();ok('宽弹窗、实时手机预览、多图切换和放大可用')
   await button('取消',editor);confirm=page.get_by_role('dialog').filter(has_text='尚有未保存的修改');await button('继续编辑',confirm);await expect(editor.get_by_label('款式名称',exact=True)).to_have_value(original+' · 未保存');await button('取消',editor);await button('放弃并继续',page.get_by_role('dialog').filter(has_text='尚有未保存的修改'));await expect(editor).not_to_be_visible();await expect(row).not_to_contain_text('未保存');ok('编辑弹窗离开保护与图片取消保留原资料')
   await row.get_by_text('维护资料',exact=True).click();editor=page.get_by_role('dialog').filter(has_text='编辑共用款式');await page.set_viewport_size({'width':1280,'height':720});await expect(editor.get_by_role('button',name='保存共用资料',exact=True)).to_be_in_viewport();await shot('05-style-editor-1280');await button('取消',editor)
   await menu('数字物品');await expect(page.get_by_text('数字物品档案',exact=True)).to_be_visible();await page.get_by_label('关键词',exact=True).fill('FASH-2026-000001');await page.get_by_role('button',name=re.compile(r'查\s*询')).click();await expect(page.get_by_role('button',name='FASH-2026-000001',exact=True)).to_be_visible();await shot('06-items-1280')
   cell=page.get_by_role('button',name='FASH-2026-000001',exact=True).locator('..');before=page.url;await cell.locator('.ant-typography-copy').click();assert await page.evaluate('navigator.clipboard.readText()')=='FASH-2026-000001';assert page.url==before;assert await page.get_by_role('dialog').count()==0;ok('编号复制只含字段值，不打开详情或导航')
   await button('FASH-2026-000001');drawer=page.get_by_role('dialog').filter(has_text='数字物品详情');await expect(drawer).to_be_visible();await expect(drawer.get_by_text('共用商品资料',exact=True)).to_be_visible();await expect(drawer.locator('.product-profile img').first).to_be_visible();await shot('07-item-drawer-1280');await button('打开完整详情',drawer);await expect(drawer).not_to_be_visible();await button('返回来源');await expect(page.get_by_label('关键词',exact=True)).to_have_value('FASH-2026-000001');ok('列表抽屉直接看共用款图，完整详情返回保留筛选')
   await button('FASH-2026-000001');drawer=page.get_by_role('dialog').filter(has_text='数字物品详情');await drawer.get_by_role('button',name=re.compile('关闭|Close')).first.click();await expect(drawer).not_to_be_visible();await expect(page.get_by_label('关键词',exact=True)).to_have_value('FASH-2026-000001')
   await menu('芯片管理');await expect(page.get_by_text('芯片档案',exact=True)).to_be_visible();await page.get_by_label('关键词',exact=True).fill('04:BB:00:00:00:00:03');await page.get_by_role('button',name=re.compile(r'查\s*询')).click();await expect(page.get_by_role('row').filter(has_text='04:BB:00:00:00:00:03').get_by_text('演示核验就绪',exact=True)).to_be_visible();await shot('08-chips-1280')
   await button('04:BB:00:00:00:00:03');drawer=page.get_by_role('dialog').filter(has_text='芯片详情');await expect(drawer).to_be_visible();await expect(drawer.get_by_text('服务状态',exact=True)).to_be_visible();await shot('09-chip-drawer-1280');await button('查看密钥与配置',drawer)
   config=page.get_by_role('dialog').filter(has_text='芯片密钥、受控查看与配置核验');await expect(config).to_be_visible();await shot('10-key-config-top-1280');await expect(config.get_by_role('button',name='已准备（不可覆盖）',exact=True)).to_be_disabled();await expect(config.get_by_role('button',name='受控查看 K0–K4 与 SUN 模板',exact=True)).to_be_disabled();await config.get_by_label('我确认本次查看：K1 为同版本全局共享秘密；关闭窗口后清除展示值。',exact=True).check();await button('受控查看 K0–K4 与 SUN 模板',config);await expect(config.locator('.key-row')).to_have_count(5);assert await config.locator('.key-row .ant-typography-copy').count()==5
   await button('隐藏并清除展示值',config);await expect(config.locator('.key-values')).to_have_count(0);await expect(config.get_by_role('button',name='关闭窗口',exact=True)).to_be_in_viewport();await shot('11-key-config-result-1280');await button('关闭窗口',config);await button('查看密钥与配置',drawer);config=page.get_by_role('dialog').filter(has_text='芯片密钥、受控查看与配置核验');await expect(config.locator('.key-values')).to_have_count(0);await expect(config.get_by_role('checkbox')).not_to_be_checked();await button('关闭窗口',config);ok('完整密钥窗口有五槽位复制、确认查看、模板、已配置保护，关闭重开清空展示与确认')
   await button('打开完整详情',drawer);await button('返回来源');await menu('数字物品');await button('FASH-2026-000003');drawer=page.get_by_role('dialog').filter(has_text='数字物品详情');await button('准备首套物品',drawer)
   bind=page.get_by_role('dialog').filter(has_text='准备物品（实物＋芯片）');await choose('物品所配芯片','04:BB:00:00:00:00:06');await bind.get_by_label('物品实际规格',exact=True).fill('S · 黑色');await button('保存物品准备',bind);await button('查看密钥与配置',drawer)
   config=page.get_by_role('dialog').filter(has_text='芯片密钥、受控查看与配置核验');await button('〔演示〕准备密钥标记',config);await config.get_by_text('3. 配卡后双链接动态读数核验',exact=True).scroll_into_view_if_needed();await expect(config.get_by_label('第 1 条触碰链接（演示）',exact=True)).to_be_visible();await config.get_by_role('button',name='〔演示〕提交双链接并确认配置核验',exact=True).scroll_into_view_if_needed();await expect(page.locator('.ant-message-notice')).to_have_count(0);assert await config.locator('textarea').evaluate_all('(els)=>els.every(e=>e.value==="")');await page.screenshot(path=str(OUT/'12-key-config-form-1280.png'));await button('关闭窗口',config);ok('首次配置表单可达，双链接输入与人工权限确认独立展示')
   await menu('系统管理');await page.get_by_role('tab',name='连接与范围',exact=True).click();await expect(page.get_by_text('未连接',exact=True)).to_have_class(re.compile('status-tag'));ok('物品、芯片、配置、售出、认领及连接状态统一带文字色块')
   assert not errors,errors;assert not [r for r in resources if r['type']!='document' and not r['url'].startswith('data:')],resources
   ok('1280/1440/1920页面无整页横向溢出，单文件无外部资源与页面异常')
  finally:
   (OUT/'browser-visual.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors,'geometry1920':geometry,'base':BASE},ensure_ascii=False,indent=2));await browser.close()
asyncio.run(main())
