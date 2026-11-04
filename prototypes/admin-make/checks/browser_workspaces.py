"""检查新工作区的视觉布局、加载/空/失败状态和演示恢复。"""
import json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
url=sys.argv[1];out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[]
def passed(name):checks.append({'case':name,'status':'passed'});print('通过：'+name,flush=True)
def mode(page,label):page.get_by_role('button',name='原型演示 · 样例数据',exact=True).click();page.get_by_role('menuitem',name=label,exact=True).click()
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1600,'height':1000});page.set_default_timeout(8000);page.on('pageerror',lambda e:errors.append(str(e)))
 try:
  page.goto(url,wait_until='networkidle');page.get_by_role('button',name='使用演示身份进入').click();page.get_by_role('menuitem',name=re.compile('物品管理')).click()
  for index,name in enumerate(['数字物品','款式资料','发行约定','办理记录']):
   page.get_by_role('tab',name=name,exact=True).click();expect(page.locator('.ant-table:visible').first).to_be_visible();page.screenshot(path=str(out/f'workspace-{index+1}.png'));assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');passed(name+'工作区表格及操作可见，无页面横向溢出')
  page.get_by_role('tab',name='款式资料',exact=True).click();mode(page,'〔演示〕列表加载中');expect(page.locator('.ant-spin-spinning')).to_be_visible();mode(page,'恢复正常演示');expect(page.locator('.ant-spin-spinning')).to_have_count(0);passed('加载中状态有明确反馈，可通过标记的演示入口恢复')
  mode(page,'列表读取失败');expect(page.get_by_role('tabpanel',name='款式资料',exact=True).get_by_text('资料列表读取失败',exact=True)).to_be_visible();page.get_by_role('tabpanel',name='款式资料',exact=True).get_by_role('button',name='重试读取',exact=True).click();expect(page.locator('.ant-table:visible').first).to_be_visible();passed('读取失败不冒充空表，重试恢复已保存资料')
  page.get_by_placeholder('款式编号或名称').fill('不存在的演示款式');page.get_by_placeholder('款式编号或名称').press('Enter');expect(page.get_by_text('没有符合条件的款式',exact=True)).to_be_visible();page.screenshot(path=str(out/'catalog-empty.png'));page.get_by_role('tabpanel',name='款式资料',exact=True).get_by_role('button',name=re.compile(r'^重\s*置$')).click();expect(page.get_by_text('没有符合条件的款式',exact=True)).to_be_hidden();passed('无匹配结果显示独立空状态，重置后恢复列表')
  page.set_viewport_size({'width':1280,'height':720});page.get_by_role('tab',name='办理记录',exact=True).click();page.screenshot(path=str(out/'works-1280.png'));assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');passed('1280×720下办理列表内部横向滚动，主页面不溢出')
  assert not errors,errors
 except Exception as exc:
  page.screenshot(path=str(out/'workspaces-failure.png'));checks.append({'case':'当前路径','status':'failed','error':str(exc)});raise
 finally:
  (out/'browser-workspaces.json').write_text(json.dumps({'results':checks,'page_errors':errors},ensure_ascii=False,indent=2));b.close()
