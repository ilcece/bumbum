"""新版款图编码与旧图片入口退役检查；历史离线备份另有恢复测试。"""
from io import BytesIO
from PIL import Image
import pytest
from core.admin_auth import AuthRequestError
from core.admin_media import encode_image

@pytest.mark.parametrize('format,mode',[('PNG','RGBA'),('JPEG','RGB'),('WEBP','RGB')])
def test_static_images_reencode_to_bounded_webp(format,mode):
    image=Image.new(mode,(2100,600),'blue');out=BytesIO();image.save(out,format=format)
    data,size=encode_image(out.getvalue())
    assert size==(2048,585)
    with Image.open(BytesIO(data)) as result:assert result.format=='WEBP' and result.n_frames==1 and not result.getexif()

@pytest.mark.parametrize('raw',[b'',b'<svg></svg>',b'GIF89a',b'not an image'])
def test_invalid_images_rejected(raw):
    with pytest.raises(AuthRequestError):encode_image(raw)

def test_animation_rejected():
    out=BytesIO();a=Image.new('RGBA',(5,5),'blue');b=Image.new('RGBA',(5,5),'red');a.save(out,format='PNG',save_all=True,append_images=[b])
    with pytest.raises(AuthRequestError):encode_image(out.getvalue())
