"""从界面新建约定与物品，验证限定/非限定引用和身份边界；不调用真实服务。"""
import json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
url=sys.argv[1];out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];requests=[]
def passed(name):checks.append({'case':name,'status':'passed'});print('通过：'+name,flush=True)
def raw(p):return p.evaluate("JSON.parse(sessionStorage.getItem('bumbum-make-prototype-v5'))")
def modal(p):return p.locator('.ant-modal:visible').last
def tab(p,name):p.get_by_role('tab',name=name,exact=True).click()
def select(p,field,text):
 field.click();p.locator('.ant-select-dropdown:visible').get_by_text(text,exact=True).last.click();expect(p.locator('.ant-select-dropdown:visible')).to_have_count(0)
def create_issue(p,name,unlimited=False,style_label='BB-TEE-BLK · BUMBUM 限定系列 T 恤 · 黑色'):
 tab(p,'发行约定');p.get_by_role('button',name='新建发行草案',exact=True).click();e=modal(p)
 e.get_by_label('发行名称',exact=True).fill(name);select(p,e.get_by_label('关联款式',exact=True),style_label)
 e.get_by_label('适用版本标记',exact=True).fill('演示版本1');select(p,e.get_by_label('发行类型',exact=True),'非限定' if unlimited else '限定')
 if unlimited:expect(e.get_by_label('发行总量',exact=True)).to_have_count(0)
 else:e.get_by_label('发行总量',exact=True).fill('3')
 e.get_by_label('允许颜色及例外约定',exact=True).fill('黑色');e.get_by_label('发行说明与权益约定',exact=True).fill('本次仅核对编号和关联，不新增未批准权益。')
 e.get_by_role('button',name='保存发行草案',exact=True).click();expect(e).to_be_hidden();issue=next(i for i in raw(p)['issuances'] if i['name']==name);assert issue['status']=='draft';return issue

def confirm_issue(p,name):
 row=p.get_by_role('row').filter(has_text=name);row.get_by_role('button',name='维护草案',exact=True).click();e=modal(p);e.get_by_role('button',name='确认发行约定',exact=True).click();modal(p).get_by_role('button',name='确认约定',exact=True).click();expect(e).to_be_hidden()

def open_create(p,name,unlimited=False):
 tab(p,'数字物品');p.get_by_role('button',name=re.compile('创建物品草稿$')).click();e=modal(p);select(p,e.get_by_role('combobox'),name+(' · 非限定／总量不限' if unlimited else ' · 限定3份'));return e

def submit(e,uid,num):
 e.get_by_placeholder('FASH-2026-000007').fill(uid);e.get_by_role('spinbutton',name='本件序号').fill(str(num));e.get_by_role('button',name='创建并继续',exact=True).click()
with sync_playwright() as pw:
 b=pw.chromium.launch(args=['--no-sandbox']);p=b.new_page(viewport={'width':1600,'height':1000});p.set_default_timeout(8000);p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:requests.append(r.url) if '/api/' in r.url else None)
 try:
  p.goto(url,wait_until='networkidle');p.get_by_role('button',name='使用演示身份进入').click();p.get_by_role('menuitem',name=re.compile('物品管理')).click()
  limited=create_issue(p,'校验限定发行');assert limited['total']==3;passed('新建限定发行草案，独立保存总量/款式/承诺')
  tab(p,'数字物品');p.get_by_role('button',name=re.compile('创建物品草稿$')).click();e=modal(p);e.get_by_role('combobox').click();expect(p.locator('.ant-select-dropdown:visible').get_by_text('校验限定发行 · 限定3份',exact=True)).to_have_count(0);p.keyboard.press('Escape');e.get_by_role('button',name=re.compile(r'^取\s*消$')).click();passed('未确认草案不能用于新物品登记')
  tab(p,'发行约定');before=len(raw(p)['items']);confirm_issue(p,'校验限定发行');assert len(raw(p)['items'])==before;assert next(i for i in raw(p)['issuances'] if i['id']==limited['id'])['status']=='issued';passed('确认约定冻结承诺，不生成物品或提前启用')
  p.get_by_role('row').filter(has_text='校验限定发行').get_by_role('button',name='查看发行约定',exact=True).click();e=modal(p);expect(e.get_by_label('关联款式',exact=True)).to_be_disabled();expect(e.get_by_label('发行总量',exact=True)).to_be_disabled();expect(e.get_by_role('button',name='保存发行草案',exact=True)).to_have_count(0);e.get_by_role('button',name=re.compile(r'^关\s*闭$')).last.click();passed('确认后关联款式/总量/颜色及权益承诺不可普通改写')
  e=open_create(p,'校验限定发行');assert e.get_by_role('combobox').count()==1;expect(e.locator('input[readonly]').nth(0)).to_have_value('BB-TEE-BLK · BUMBUM 限定系列 T 恤 · 黑色');expect(e.locator('input[readonly]').nth(1)).to_have_value('服装');passed('新建只选发行，款式与类别自动引用且只读')
  submit(e,'FASH-2026-888001',4);expect(e.get_by_text('本件序号超出限定发行总量。',exact=True)).to_be_visible();assert len(raw(p)['items'])==before;passed('限定序号超过总量被拒绝且不产生半条身份')
  submit(e,'FASH-2026-888001',1);expect(e.get_by_placeholder('FASH-2026-000007')).to_have_value('');item=raw(p)['items'][0];m=raw(p)['identities'][str(item['id'])];assert m['issuanceId']==limited['id'] and m['editionNumber']==1 and item['styleId']==limited['styleId'];assert item['status']=='draft' and item['bound_chip_id'] is None and m['ownerId'] is None;passed('创建时原子保存物品/发行/序号，仍未绑定未归属未启用')
  expect(e.get_by_role('spinbutton',name='本件序号')).to_have_value('2');submit(e,'FASH-2026-888002',1);expect(e.get_by_text('该发行内的本件序号已占用。',exact=True)).to_be_visible();assert len(raw(p)['items'])==before+1;passed('连续创建保留发行，重复发行内序号拒绝覆盖')
  submit(e,'FASH-2026-888001',2);expect(e.get_by_text(re.compile('已存在编号'))).to_be_visible();assert len(raw(p)['items'])==before+1;passed('系统物品编号与本件序号分开检查，重复身份不覆盖')
  submit(e,'FASH-2026-888002',2);expect(e.get_by_placeholder('FASH-2026-000007')).to_have_value('');e.get_by_role('button',name=re.compile(r'^取\s*消$')).click()
  unlimited=create_issue(p,'校验非限定发行',True);assert unlimited['total'] is None;confirm_issue(p,'校验非限定发行');passed('非限定草案保存无总量并可确认，仍绑定款式承诺')
  e=open_create(p,'校验非限定发行',True);p.set_viewport_size({'width':1280,'height':720});e.get_by_role('button',name='创建并继续',exact=True).scroll_into_view_if_needed();box=e.get_by_role('button',name='创建并继续',exact=True).bounding_box();assert box['y']>=0 and box['y']+box['height']<=720;p.screenshot(path=str(out/'unlimited-create-1280.png'),animations='disabled');passed('新增发行字段后1280×720物品创建弹窗操作仍可达');p.set_viewport_size({'width':1600,'height':1000});submit(e,'FASH-2026-888003',125);expect(e.get_by_placeholder('FASH-2026-000007')).to_have_value('');item=raw(p)['items'][0];m=raw(p)['identities'][str(item['id'])];assert m['issuanceId']==unlimited['id'] and m['editionNumber']==125;e.get_by_role('button',name=re.compile(r'^取\s*消$')).click();passed('非限定允许大于100的本件序号，无发行数量上限')
  search=p.get_by_placeholder('搜索物品编号、款式、名称或芯片 UID',exact=True);search.fill('FASH-2026-888003');search.press('Enter');p.get_by_role('button',name='FASH-2026-888003',exact=True).click();d=p.locator('.ant-drawer:visible');expect(d.get_by_text('#125',exact=True)).to_be_visible();expect(d.get_by_text('#125/null',exact=True)).to_have_count(0);d.get_by_text('查看共用资料',exact=True).click();facts=modal(p);expect(facts.get_by_text('非限定 · 总量不限',exact=True)).to_be_visible();expect(facts.get_by_text('未配置权益规则',exact=True)).to_be_visible();facts.get_by_role('button',name=re.compile(r'^关\s*闭$')).last.click();p.screenshot(path=str(out/'unlimited-item-detail.png'),animations='disabled');d.get_by_role('button',name='维护身份关联',exact=True).click();e=modal(p);expect(e.get_by_label('关联发行记录',exact=True)).to_be_disabled();expect(e.get_by_label('本件序号',exact=True)).to_have_attribute('readonly','');e.get_by_role('button',name=re.compile(r'^取\s*消$')).click();d.locator('.ant-drawer-close').click();passed('非限定详情仅显示本件编号，已登记身份不能普通重分配')
  p.reload(wait_until='networkidle');p.get_by_role('button',name='使用演示身份进入').click();assert next(m for m in raw(p)['identities'].values() if m['issuanceId']==unlimited['id'])['editionNumber']==125;passed('刷新后保留准确发行引用与非限定序号')
  tab(p,'发行约定');p.get_by_role('row').filter(has_text='校验非限定发行').get_by_role('button',name='查看发行约定',exact=True).click();e=modal(p);expect(e.get_by_label('发行类型',exact=True)).to_be_disabled();expect(e.get_by_label('发行总量',exact=True)).to_have_count(0);p.screenshot(path=str(out/'unlimited-issuance.png'),animations='disabled');passed('非限定约定详情不伪造总量或限定规则')
  e.get_by_role('button',name=re.compile(r'^关\s*闭$')).last.click()
  data=raw(p);legacy=next(i for i in data['items'] if i['status']=='draft' and not i['bound_chip_id'] and not data['identities'].get(str(i['id']),{}).get('issuanceId') and not data['identities'].get(str(i['id']),{}).get('ownerId'));style=next(s for s in data['styles'] if s['id']==legacy['styleId'])
  legacy_issue=create_issue(p,'旧草稿补关联约定',True,style['code']+' · '+style['profile']['name']);confirm_issue(p,'旧草稿补关联约定');tab(p,'数字物品');search=p.get_by_placeholder('搜索物品编号、款式、名称或芯片 UID',exact=True);search.fill(legacy['item_uid']);search.press('Enter');p.get_by_role('button',name=legacy['item_uid'],exact=True).click();d=p.locator('.ant-drawer:visible');d.get_by_role('button',name='维护身份关联',exact=True).click();e=modal(p);select(p,e.get_by_label('关联发行记录',exact=True),'旧草稿补关联约定 · 非限定／不限');e.get_by_label('本件序号',exact=True).fill('17');e.get_by_role('button',name='保存关联',exact=True).click();expect(e).to_be_hidden();meta=raw(p)['identities'][str(legacy['id'])];assert meta['issuanceId']==legacy_issue['id'] and meta['editionNumber']==17;assert next(i for i in raw(p)['items'] if i['id']==legacy['id'])==legacy;passed('旧的未绑定未归属草稿可补同款约定与序号，其他物品事实不变')
  d.locator('.ant-drawer-close').click();search.fill('FASH-2026-000001');search.press('Enter');p.get_by_role('button',name='FASH-2026-000001',exact=True).click();expect(p.locator('.ant-drawer:visible').get_by_role('button',name='维护身份关联',exact=True)).to_be_disabled();passed('已启用/绑定/归属身份不开放普通重分配')
  assert not errors,errors;assert not requests,requests;passed('全程无页面运行错误及真实业务请求')
 except Exception as exc:
  p.screenshot(path=str(out/'issuance-failure.png'));checks.append({'case':'当前路径','status':'failed','error':str(exc)});raise
 finally:
  (out/'browser-issuance.json').write_text(json.dumps({'results':checks,'page_errors':errors,'business_requests':requests},ensure_ascii=False,indent=2));b.close()
