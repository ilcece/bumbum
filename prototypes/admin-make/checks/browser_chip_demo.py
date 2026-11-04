"""验证显式标记的Webhook登记到芯片配置核验原型链路，不访问真实设备。"""
import json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
url=sys.argv[1];out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];requests=[]
def passed(name):checks.append({'case':name,'status':'passed'});print('通过：'+name,flush=True)
def raw(page):return page.evaluate("JSON.parse(sessionStorage.getItem('bumbum-make-prototype-v4'))")
def modal(page):return page.locator('.ant-modal:visible').last
def menu(page,name):page.get_by_role('menuitem',name=re.compile(name)).click()
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1600,'height':1000});page.set_default_timeout(8000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url) if '/api/' in r.url else None)
 try:
  page.goto(url,wait_until='networkidle');page.get_by_role('button',name='使用演示身份进入').click();menu(page,'物品管理');page.get_by_role('button',name=re.compile('创建物品草稿$')).click();e=modal(page);e.get_by_role('combobox').click();page.locator('.ant-select-dropdown:visible .ant-select-item-option:visible').first.click();expect(page.locator('.ant-select-dropdown:visible')).to_have_count(0);e.get_by_placeholder('FASH-2026-000007').fill('FASH-2026-999902');e.get_by_role('button',name='创建并继续',exact=True).click();expect(e.get_by_placeholder('FASH-2026-000007')).to_have_value('');e.get_by_role('button',name=re.compile(r'^取\s*消$')).click();item=next(i for i in raw(page)['items'] if i['item_uid']=='FASH-2026-999902');passed('为Webhook配卡链路创建确切款式引用的物品草稿')
  menu(page,'芯片管理');page.get_by_role('button',name='〔演示〕触发Webhook登记',exact=True).click();expect(page.get_by_text(re.compile('〔演示〕Webhook已登记'))).to_be_visible();chip=raw(page)['chips'][0];page.get_by_role('button',name=re.compile('立即绑定物品$')).click();e=modal(page);e.get_by_placeholder('搜索物品编号、款式编号或名称').fill('FASH-2026-999902');row=e.get_by_role('row').filter(has_text='FASH-2026-999902');row.get_by_role('radio').click();e.get_by_role('checkbox').check();e.get_by_role('button',name='确认首次绑定',exact=True).click();expect(e).to_be_hidden();bound=next(c for c in raw(page)['chips'] if c['id']==chip['id']);assert bound['item_id']==item['id'] and bound['keys_generated'] is False;passed('Webhook登记后可首次关联物品，绑定不提前生成密钥或核验')
  page.get_by_role('button',name=re.compile('继续生成密钥与配卡核验$')).click();e=page.get_by_role('dialog',name='芯片密钥生成、受控查看与实卡配置核验',exact=True);expect(e.get_by_text('芯片配卡交互演示',exact=True)).to_be_visible();e.get_by_role('button',name='〔演示〕生成芯片密钥标记',exact=True).click();expect(e.get_by_role('button',name='密钥已生成 (不可覆盖)',exact=True)).to_be_disabled();assert next(c for c in raw(page)['chips'] if c['id']==chip['id'])['provisioned_at'] is None;passed('演示密钥准备标记不可覆盖，不自动完成配置核验')
  e.get_by_role('checkbox',name=re.compile('我确认查看密钥')).check();e.get_by_role('button',name='〔演示〕查看密钥占位与模板',exact=True).click();expect(e.get_by_text('演示占位值，不是真实密钥',exact=True)).to_have_count(5);passed('受控查看演示仅显示占位文字，不产生真实密钥')
  e.get_by_role('button',name='〔演示〕填入两条递增链接',exact=True).click();e.get_by_role('checkbox',name=re.compile('我已人工核对新 K0')).check();e.get_by_role('button',name='〔演示〕提交双链接核验样例',exact=True).click();expect(e.get_by_text('〔演示〕配置核验通过样例已记录；未校验真实卡片或凭证。',exact=True)).to_be_visible();updated=next(c for c in raw(page)['chips'] if c['id']==chip['id']);assert updated['provisioned_at'] is not None;assert raw(page)['items'][0]['id']==item['id'];assert not next((m for key,m in raw(page)['identities'].items() if int(key)==item['id']),{}).get('ownerId');page.screenshot(path=str(out/'chip-provision-demo.png'));passed('递增链接与人工确认位置保留，核验样例不认领所有人')
  assert not errors,errors;assert not requests,requests;passed('完整Webhook/配卡演示无运行异常或真实业务请求')
 except Exception as exc:
  page.screenshot(path=str(out/'chip-demo-failure.png'));checks.append({'case':'当前路径','status':'failed','error':str(exc)});raise
 finally:
  (out/'browser-chip-demo.json').write_text(json.dumps({'results':checks,'page_errors':errors,'business_requests':requests},ensure_ascii=False,indent=2));b.close()
