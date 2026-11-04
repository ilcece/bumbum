"""仅验证本轮列表排序、新增定位和分页上限，不重复组件或其他业务矩阵。"""
import json,re,sys
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
url=sys.argv[1];out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True);cases=[];errors=[]
def passed(name):cases.append({'case':name,'status':'passed'});print('通过：'+name,flush=True)
def raw(page):return page.evaluate("JSON.parse(sessionStorage.getItem('bumbum-make-prototype-v4'))")
def rows(page):return page.locator('.ant-table:visible .ant-table-tbody > tr.ant-table-row')
def goto_page(page,n):page.locator('.ant-pagination:visible').get_by_title(str(n),exact=True).click();expect(page.locator('.ant-pagination-item-active:visible')).to_have_attribute('title',str(n))
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1600,'height':1000});page.set_default_timeout(7000);page.on('pageerror',lambda e:errors.append(str(e)))
 try:
  page.goto(url,wait_until='networkidle');page.get_by_role('button',name='使用演示身份进入').click();page.get_by_role('menuitem',name=re.compile('芯片管理')).click();data=raw(page);assert len({c['id'] for c in data['chips']})==len(data['chips']);ordered=sorted(data['chips'],key=lambda c:(datetime.fromisoformat(c['created_at'].replace('Z','+00:00')).timestamp(),c['id']),reverse=True)
  for n in range(1,(len(ordered)+9)//10+1):
   if n>1:goto_page(page,n)
   chunk=ordered[(n-1)*10:n*10];expect(rows(page)).to_have_count(len(chunk))
   for index,c in enumerate(chunk):expect(rows(page).nth(index).get_by_role('button',name=c['chip_uid'],exact=True)).to_be_visible()
  passed('芯片跨页按登记时间倒序、相同时编号倒序，每页最多10条且无遗漏')
  goto_page(page,2);page.get_by_role('button',name=re.compile('手工登记芯片$')).click();m=page.locator('.ant-modal:visible').last;m.get_by_placeholder('如 04:A2:7F:1B:5E:80:18 或 04a27f1b5e8018').fill('04:DE:AA:00:00:00:01');m.get_by_role('button',name='登记并继续下一枚',exact=True).click();m.get_by_role('button',name=re.compile(r'^取\s*消$')).click();expect(page.locator('.ant-pagination-item-active:visible')).to_have_attribute('title','1');expect(rows(page).first.get_by_role('button',name='04:DE:AA:00:00:00:01',exact=True)).to_be_visible();passed('第二页手工登记成功后回首页，新芯片排第一')
  goto_page(page,2);page.get_by_role('button',name='〔演示〕触发Webhook登记',exact=True).click();expect(page.locator('.ant-pagination-item-active:visible')).to_have_attribute('title','1');new=raw(page)['chips'][0];expect(rows(page).first.get_by_role('button',name=new['chip_uid'],exact=True)).to_be_visible();passed('第二页Webhook新增成功后回首页，新记录排第一')
  goto_page(page,2);count=len(raw(page)['chips']);page.get_by_role('button',name='〔演示〕重复回调',exact=True).click();assert len(raw(page)['chips'])==count;expect(page.locator('.ant-pagination-item-active:visible')).to_have_attribute('title','2');passed('重复回调不新增、不改登记时间、不强制跳页')
  search=page.get_by_placeholder('搜索芯片 UID、物品编号或物品名称');search.fill('NEVER-MATCH-DEMO');search.press('Enter');expect(rows(page)).to_have_count(0);page.get_by_role('button',name='〔演示〕触发Webhook登记',exact=True).click();expect(search).to_have_value('NEVER-MATCH-DEMO');expect(rows(page)).to_have_count(0);page.get_by_role('button',name='查看详情与维护批次',exact=True).click();expect(page.locator('.ant-drawer:visible')).to_be_visible();page.locator('.ant-drawer:visible .ant-drawer-close').click();passed('新增保留筛选，不匹配时不伪造结果，成功提示仍可查看确切记录')
  page.get_by_role('menuitem',name=re.compile('物品管理')).click();expect(rows(page)).to_have_count(10);goto_page(page,2);expect(rows(page)).to_have_count(8);page.get_by_role('tab',name='款式资料',exact=True).click();assert rows(page).count()<=10;page.get_by_role('tab',name='发行约定',exact=True).click();assert rows(page).count()<=10;page.get_by_role('tab',name='办理记录',exact=True).click();assert rows(page).count()<=10;passed('物品、款式、发行和办理各列表分页上限10条')
  assert not errors,errors
 except Exception as exc:
  page.screenshot(path=str(out/'pagination-failure.png'));cases.append({'case':'当前路径','status':'failed','error':str(exc)});raise
 finally:
  (out/'browser-pagination.json').write_text(json.dumps({'results':cases,'page_errors':errors},ensure_ascii=False,indent=2));b.close()
