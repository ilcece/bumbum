"""新版款式图片的公共静态图片编码器；旧单件图片服务已退役。"""
from io import BytesIO
import warnings
from PIL import Image,ImageOps,UnidentifiedImageError,WebPImagePlugin
from werkzeug.formparser import FormDataParser,MultiPartParser
from core.admin_auth import AuthRequestError
from core.media_assets import MAX_FILE,MAX_PIXELS,MAX_WEBP_PIXELS,init_media_settings

def encode_image(raw):
    """完整解码静态图片，按方向缩小并重编码；不保存原文件或元数据。"""
    try:
        with warnings.catch_warnings():
            # 8–16MP的警告由下方明确上限接管；超16MP仍由Pillow硬拒绝。
            warnings.simplefilter('ignore', Image.DecompressionBombWarning)
            if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
                # 锁定Pillow13的头部尺寸识别在分配WebP解码画布前执行；不自行解码。
                size = WebPImagePlugin._get_size(raw[:30])
                if size is None or size[0] * size[1] > MAX_WEBP_PIXELS:
                    raise ValueError
            with Image.open(BytesIO(raw)) as image:
                limit = MAX_WEBP_PIXELS if image.format == 'WEBP' else MAX_PIXELS
                if image.format not in {'JPEG', 'PNG', 'WEBP'} or image.width * image.height > limit or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError
                image.load()
                image.thumbnail((2048, 2048), reducing_gap=3.0)
                # 先缩小再旋转，避免方向修正同时持有两份1600万像素图像。
                ImageOps.exif_transpose(image, in_place=True)
                if image.mode not in {'RGB', 'RGBA'}:
                    image = image.convert('RGBA' if 'transparency' in image.info or 'A' in image.getbands() else 'RGB')
                image.info.clear()
                output = BytesIO()
                image.save(output, format='WEBP', quality=85, method=4)
                encoded, size = output.getvalue(), image.size
        if not 0 < len(encoded) <= MAX_FILE:
            raise ValueError
        return encoded, size
    except (UnidentifiedImageError, OSError, EOFError, SyntaxError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise AuthRequestError(400, 'invalid_param', '请选择完整静态JPEG/PNG（最多1600万像素）或WebP（最多800万像素），单张8MiB；不接受损坏或多帧图片。') from None


def init_media(app):
    init_media_settings(app)


class UploadFormDataParser(FormDataParser):
    """小块解析multipart，保持文字限制且允许受限大小的图片。"""
    def _parse_multipart(self,stream,mimetype,content_length,options):
        parser=MultiPartParser(stream_factory=self.stream_factory,max_form_memory_size=self.max_form_memory_size,max_form_parts=self.max_form_parts,cls=self.cls,buffer_size=16*1024)
        boundary=options.get('boundary','').encode('ascii')
        if not boundary:raise ValueError('缺少multipart边界。')
        form,files=parser.parse(stream,boundary,content_length)
        return stream,form,files
