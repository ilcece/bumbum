"""同尺寸对照已验收原型源码，并验证先选图再保存及部分失败恢复。"""
from pathlib import Path
from io import BytesIO
import re
import pytest
from PIL import Image
from tests.test_admin_browser import browser_gate, desktop, button, expect
from tests.test_admin_auth import query

pytestmark=[pytest.mark.auth_database,pytest.mark.browser]

def test_style_source_layout_and_staged_picture_save(desktop):
    p=desktop.page;desktop.app.config['MEDIA_ENABLED']=True
    desktop.login();p.goto('http://localhost:5174/catalog/style/new',wait_until='networkidle')
    reference_context=p.context.browser.new_context();reference=reference_context.new_page();reference.goto((Path('prototypes/admin-make/preview.html').resolve()).as_uri())
    reference.get_by_role('button',name='使用演示身份进入',exact=True).click()
    reference.get_by_role('link',name=re.compile('款式与发行$')).click()
    reference.get_by_role('button',name='新建款式',exact=True).click()
    out=Path('test-results/style-fidelity');out.mkdir(parents=True,exist_ok=True)
    for width,height in ((1440,900),(1920,1080)):
        p.set_viewport_size({'width':width,'height':height});reference.set_viewport_size({'width':width,'height':height})
        for page,name in ((reference,'reference'),(p,'actual')):
            expect(page.get_by_text('共用商品资料',exact=True)).to_be_visible()
            expect(page.get_by_role('button',name='保存共用资料',exact=True)).to_be_visible()
            page.screenshot(path=str(out/f'{name}-{width}.png'),animations='disabled')
        # 对照布局和控件的实际边界，不以元素存在代替视觉核对。
        for selector in ('.style-editor-grid','.mobile-preview','.editor-footer'):
            actual=p.locator(selector).bounding_box();expected=reference.locator(selector).bounding_box()
            assert actual and expected
            for axis in ('x','y','width','height'):
                # 本轮明确将参考图片段落改为标准表单标签，容器增高10px；其余定位继续对照冻结原型。
                tolerance=16 if selector=='.style-editor-grid' and axis=='height' else 8
                assert abs(actual[axis]-expected[axis])<tolerance,(selector,axis,actual,expected)
        expect(p.get_by_label('适用规格（每行一项）',exact=True)).to_have_attribute('rows','3')
    reference_context.close()
    p.get_by_label('款式编号',exact=True).fill('SOURCE-STYLE')
    p.get_by_label('款式名称',exact=True).fill('对照原型的商品')
    p.get_by_label('适用规格（每行一项）',exact=True).fill('L黑\nM白')
    image=BytesIO();Image.new('RGB',(32,24),'blue').save(image,format='PNG')
    p.locator('input[type=file]').set_input_files({'name':'staged.png','mimeType':'image/png','buffer':image.getvalue()})
    expect(p.get_by_alt_text('商品图片 1',exact=True)).to_be_visible()
    expect(p.get_by_text('第 1 张 · staged.png · 待保存 · 列表首图',exact=True)).to_be_visible()
    assert query(desktop.app,'SELECT COUNT(*) AS n FROM product_style')[0]['n']==0
    assert query(desktop.app,'SELECT COUNT(*) AS n FROM style_image')[0]['n']==0
    p.screenshot(path=str(out/'staged-preview.png'),animations='disabled')
    # 模拟上传结果丢失；再次明确保存必须先查原上传，且不重复建款/上传。
    writes=[]
    def lost(route):
        writes.append(1);response=route.fetch();assert response.status==200
        route.fulfill(status=503,json={'status':'error','code':'service_unavailable','message':'隔离模拟上传回执丢失'})
    path='**/api/admin/catalog/styles/*/images/*';p.route(path,lost)
    button(p,'保存共用资料')
    expect(p.get_by_text('款式资料已保存，仍有图片待保存；请继续完成或明确放弃未保存部分。',exact=True)).to_be_visible()
    assert query(desktop.app,'SELECT COUNT(*) AS n FROM product_style')[0]['n']==1
    p.unroute(path,lost);button(p,'保存共用资料')
    p.wait_for_url(re.compile(r'/catalog/style/[0-9]+$'))
    expect(p.get_by_text('对照原型的商品',exact=True)).to_be_visible()
    assert query(desktop.app,'SELECT COUNT(*) AS n FROM product_style')[0]['n']==1
    assert query(desktop.app,'SELECT COUNT(*) AS n FROM style_image')[0]['n']==1
    assert writes==[1]
    assert query(desktop.app,'SELECT specs FROM product_style')[0]['specs']=='["L黑", "M白"]'
    expect(p.locator('.mobile-preview-header')).to_contain_text('已保存内容')
    p.get_by_label('款式名称',exact=True).fill('保存后继续修改')
    p.get_by_role('link',name=re.compile('数字物品$')).click()
    guard=p.get_by_role('dialog',name='有未保存修改',exact=True)
    expect(guard).to_be_visible();button(guard,'继续编辑')
    expect(p.get_by_label('款式名称',exact=True)).to_have_value('保存后继续修改')
