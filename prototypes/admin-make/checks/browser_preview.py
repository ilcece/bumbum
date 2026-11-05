"""检查离线交付件及用户指定的主要容器尺寸。"""
import json,re,sys,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
out=Path(sys.argv[1]);target=sys.argv[2] if len(sys.argv)>2 else (out/'管理后台高保真交互原型.html').as_uri();checks=[];requests=[];errors=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox']);page=b.new_page(viewport={'width':1280,'height':720});page.on('request',lambda r:requests.append(r.url) if r.url.startswith(('http:','https:')) and r.url!=target else None);page.on('pageerror',lambda e:errors.append(str(e)))
 try:
  page.goto(target,wait_until='networkidle');page.get_by_role('button',name='使用演示身份进入').click();page.get_by_role('menuitem',name=re.compile('物品与芯片')).click();page.get_by_role('button',name='FASH-2026-000001',exact=True).click();d=page.locator('.ant-drawer:visible');assert round(d.locator('.ant-drawer-content-wrapper').bounding_box()['width'])==800;checks.append({'case':'离线详情抽屉宽800px','status':'passed'});page.screenshot(path=str(out/'item-detail-800.png'))
  d.get_by_role('button',name='办理转售',exact=True).click();m=page.get_by_role('dialog',name='业务办理',exact=True);expect(m).to_be_visible();page.wait_for_timeout(350);box=m.bounding_box();assert round(box['width'])==1120;assert abs(box['x']-(1280-box['width'])/2)<2;expect(m.get_by_label('目标尺码',exact=True)).to_have_count(0);button=m.get_by_role('button',name='保存申请，进入准备',exact=True);button.scroll_into_view_if_needed();box=button.bounding_box();assert box['y']>=0 and box['y']+box['height']<=720;page.screenshot(path=str(out/'resale-centered-1120.png'));checks.append({'case':'1280×720下转售居中1120px，申请不填尺码，底部操作可达','status':'passed'})
  assert not requests,requests;assert not errors,errors;checks.append({'case':'单HTML无外部资源请求及页面运行异常','status':'passed'})
 finally:
  (out/'preview-review.json').write_text(json.dumps({'results':checks,'page_errors':errors,'network_requests':requests},ensure_ascii=False,indent=2));b.close()
print('通过：离线与容器检查',len(checks),'项')
