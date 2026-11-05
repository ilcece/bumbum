"""通过正常UI验证新版完整核心流程，不注入浏览器业务数据。"""
import asyncio,json,os
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright,expect
BASE=os.environ.get('PROTOTYPE_URL','http://127.0.0.1:8765/')
OUT=Path(os.environ.get('PROTOTYPE_EVIDENCE','/workspace/work/umi-browser'));OUT.mkdir(parents=True,exist_ok=True)
async def main():
 checks=[];errors=[];requests=[]
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  page=await browser.new_page(viewport={'width':int(os.environ.get('PROTOTYPE_WIDTH','1440')),'height':int(os.environ.get('PROTOTYPE_HEIGHT','1000'))},timezone_id='Asia/Shanghai')
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:requests.append(r.url))
  def passed(s):checks.append(s);print('通过：'+s,flush=True)
  async def button(name,root=None):await (root or page).get_by_role('button',name=name,exact=True).click()
  async def choose(label,text,root=None):
   root=root or page;field=root.get_by_label(label,exact=True);await field.click();await page.locator('.ant-select-dropdown:visible').get_by_text(text,exact=True).click()
   if '芯片' in label:await expect(field.locator('xpath=ancestor::div[contains(@class, "ant-select ")][1]').get_by_title(text,exact=True)).to_be_visible()
  async def data():return await page.evaluate("JSON.parse(sessionStorage.getItem('bumbum-pro-prototype-v6'))")
  async def configure(root=None):
   root=root or page;await button('查看密钥与配置',root)
   config=page.get_by_role('dialog').filter(has_text='芯片密钥、受控查看与配置核验')
   await button('〔演示〕准备密钥标记',config);await button('填入两条演示链接',config);await config.get_by_label('我已人工核对新 K0 可以认证且文件权限符合手册（演示确认）',exact=True).check();first_link=await config.get_by_label('第 1 条触碰链接（演示）',exact=True).input_value();await config.get_by_label('第 2 条触碰链接（演示）',exact=True).fill(first_link);await button('〔演示〕提交双链接并确认配置核验',config);await expect(config.get_by_text('仅接受当前芯片的两条递增演示链接；真实读数请使用正式配卡服务核验。',exact=True)).to_be_visible();await button('填入两条演示链接',config);await button('〔演示〕提交双链接并确认配置核验',config);await expect(config.get_by_text('演示配置核验已记录',exact=True)).to_be_visible();await button('关闭窗口',config)
  try:
   await page.goto(BASE);await button('使用演示身份进入');await expect(page.get_by_text('物品与芯片概况',exact=True)).to_be_visible()
   await page.mouse.move(1000,20);await page.screenshot(path=str(OUT/'overview.png'),full_page=True)
   await button('新建款式');await page.get_by_label('款式编号',exact=True).fill('CORE-CAP-01');await page.get_by_label('款式名称',exact=True).fill('核心流程验收帽子');await page.get_by_label('商品介绍',exact=True).fill('同一数字身份延续实体与芯片历史');await page.get_by_label('材质',exact=True).fill('棉');await page.get_by_label('适用规格（每行一项）',exact=True).fill('蓝色 · 均码')
   await button('保存共用资料');await expect(page).to_have_url(__import__('re').compile(r'/catalog/style/(?!new)'))
   await button('继续建立发行约定');await page.get_by_label('发行名称',exact=True).fill('帽子固定50身份');await page.get_by_label('固定发行总量',exact=True).fill('50');await page.get_by_label('发行说明与规格承诺',exact=True).fill('限量50个数字身份；允许换新和转售；规格按实体记录')
   await choose('适用权益','付费定期/挂失换新');await choose('适用权益','后台转售数字内容及约定权益');await page.keyboard.press('Escape')
   await button('保存发行草案');await button('确认发行约定');await button('确认发行约定',page.get_by_role('dialog'));await expect(page.get_by_text('限定50个身份',exact=True).first).to_be_visible()
   passed('新款式→保存发行草案→明确确认，独立维护页和已保存定位')
   await button('登记该发行物品');dialog=page.get_by_role('dialog');await expect(dialog.get_by_label('系统物品编号',exact=True)).not_to_be_empty();uid=await dialog.get_by_label('系统物品编号',exact=True).input_value();await button('登记并查看物品',dialog);await expect(page.get_by_text('尚无实体与芯片关联',exact=True)).to_be_visible()
   await button('启用物品');await expect(page.get_by_text('启用前需要发行、有效芯片及配置核验。',exact=True)).to_be_visible()
   await button('首次绑定芯片');dialog=page.get_by_role('dialog');await choose('待绑定芯片','04:BB:00:00:00:00:06',dialog);await dialog.get_by_label('实际实体规格',exact=True).fill('蓝色 · 均码');await button('确认首次绑定',dialog)
   await button('维护当前芯片');await configure();await button('返回来源');await button('启用物品');await expect(page.get_by_role('button',name='停用物品',exact=True)).to_be_visible()
   d=await data();item=next(i for i in d['items'] if i['uid']==uid);item_id=item['id'];assert item['ownerId'] is None and not item['sold'];passed('新身份→首次配卡→配置→启用，阻断未配置启用且不自动认领或售出')
   await button('维护售出确认');dialog=page.get_by_role('dialog');await dialog.get_by_label('销售确认或更正依据',exact=True).fill('已核对外部网店有效销售，不录订单物流');await button('保存售出确认',dialog);await expect(dialog).not_to_be_visible();d=await data();item=next(i for i in d['items'] if i['id']==item_id);assert item['sold'] and item['ownerId'] is None;sold_at=item['firstSoldAt'];passed('已售出可以未认领，独立销售标记及首次时间')
   await button('〔演示〕模拟首次认领');dialog=page.get_by_role('dialog');await choose('演示认领账户','持有人甲 · 演示账户',dialog);await button('确 定',dialog)
   await expect(dialog).not_to_be_visible();await button('〔演示〕模拟当前卡触碰');d=await data();assert len([e for e in d['touches'] if e['itemId']==item_id])==1
   await button('〔演示〕重复同一读数');await expect(page.get_by_text('同一芯片的已用读数或重复刷新不重复计次。',exact=True)).to_be_visible();passed('首次演示认领→触碰，重复读数不增加事件')
   await button('办理换新 / 转售');dialog=page.get_by_role('dialog');await choose('新实体候选芯片','04:BB:00:00:00:00:07',dialog);await dialog.get_by_label('新实体实际规格',exact=True).fill('蓝色 · 新实体');await dialog.get_by_label('资格及接收对象核对依据',exact=True).fill('核对原持有人及换新资格');await button('保存准备，继续配置候选芯片',dialog)
   await expect(dialog.get_by_text('准备阶段保留原关联与原持有人',exact=True)).to_be_visible();d=await data();assert next(c for c in d['chips'] if c['id']==6)['state']=='bound';assert next(c for c in d['chips'] if c['id']==7)['itemId'] is None
   await configure(dialog);await dialog.get_by_label('实际交付核验依据',exact=True).fill('核对实际交付、新旧实体及本人接收');await dialog.get_by_label('已核对实际交付、接收账户及新旧实体的对应关系').check();await button('确认接续',dialog);await expect(dialog.get_by_text('接续已完成，数字身份及发行编号沿用',exact=True)).to_be_visible();await button('关闭，保留接续记录',dialog)
   d=await data();item=next(i for i in d['items'] if i['id']==item_id);assert item['ownerId']=='DEMO-A' and item['quotaReview'] and item['used']==0;assert next(c for c in d['chips'] if c['id']==6)['state']=='retired';await button('〔演示〕模拟当前卡触碰');passed('换新两段接续：候选不提前授权，完成时旧卡退役、身份不增发、计次待核')
   await button('办理换新 / 转售');dialog=page.get_by_role('dialog');await choose('业务类型','后台转售',dialog);await choose('转售接收账户（仅转售必填）','持有人乙 · 演示账户',dialog);await choose('新实体候选芯片','04:BB:00:00:00:00:08',dialog);await dialog.get_by_label('新实体实际规格',exact=True).fill('蓝色 · 转售新实体');await dialog.get_by_label('资格及接收对象核对依据',exact=True).fill('转售接收账户及资格已核对');await button('保存准备，继续配置候选芯片',dialog);await configure(dialog);await dialog.get_by_label('实际交付核验依据',exact=True).fill('新实体交付给接收账户乙');await dialog.get_by_label('已核对实际交付、接收账户及新旧实体的对应关系').check();await button('确认接续',dialog);await button('关闭，保留接续记录',dialog)
   await button('〔演示〕模拟当前卡触碰');d=await data();item=next(i for i in d['items'] if i['id']==item_id);assert item['ownerId']=='DEMO-B' and item['uid']==uid and item['number']==1 and item['firstSoldAt']==sold_at and item['used']==0;assert len(item['entities'])==3 and len([e for e in d['touches'] if e['itemId']==item_id])==3
   await page.mouse.move(1000,20);await page.screenshot(path=str(OUT/'item-history.png'),full_page=True);passed('转售沿用同一身份与发行编号，变更持有人，三代芯片事件累计3次')
   await page.get_by_role('button',name='04:BB:00:00:00:00:06',exact=True).first.click();await button('〔演示〕模拟此卡触碰');await expect(page.get_by_text('当前芯片/物品不可提供有效触碰；退役、停用或候选卡不会增加次数。',exact=True)).to_be_visible();assert len([e for e in (await data())['touches'] if e['itemId']==item_id])==3;passed('从完整新建流程产生的退役卡拒绝服务，事件数不变')
   await page.get_by_role('menuitem',name=__import__('re').compile('款式与发行$')).click();await page.get_by_role('tab',name='发行约定',exact=True).click();await page.get_by_role('row').filter(has_text='棒球帽 · 限时发行').get_by_text('查看约定',exact=True).click();await button('核对并确认最终数量');dialog=page.get_by_role('dialog');print('SEAL DIALOG',await dialog.inner_text(),flush=True)
   await dialog.get_by_label('最终发行总量',exact=True).fill('137');await dialog.get_by_label('外部核定依据',exact=True).fill('多店对账汇总137，无须录入137张订单');await dialog.get_by_label('已核对有效数量及身份冲突，理解封版后不能普通改总量或重排编号').check();await button('确认最终发行结果',dialog);await expect(dialog).not_to_be_visible();d=await data();assert next(s for s in d['issues'] if s['id']=='ISS-CAP')['total']==137;assert len(d['items'])==5;passed('期满直接维护最终137个身份的发行结果，不新增订单或虚造137件物品')
   assert not errors,errors
   await page.set_viewport_size({'width':1280,'height':720});await page.screenshot(path=str(OUT/'issue-1280.png'),full_page=True)
   assert not [u for u in requests if urlsplit(u).scheme in ('http','https') and urlsplit(u).netloc!=urlsplit(BASE).netloc]
  finally:
   (OUT/'browser-core.json').write_text(json.dumps({'checks':checks,'passed':len(checks),'errors':errors,'base':BASE},ensure_ascii=False,indent=2))
   await page.screenshot(path=str(OUT/'last.png'),full_page=True)
   print('LAST_URL',page.url,flush=True);print('ERRORS',errors,flush=True)
   await browser.close()
asyncio.run(main())
