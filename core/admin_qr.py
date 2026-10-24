"""在本机临时页面显示验证器二维码，不上传秘密或提供网页设置接口。"""

from contextlib import contextmanager
from html import escape
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import webbrowser

import click
import pyotp
import qrcode
from qrcode.image.svg import SvgPathFillImage


def setup_page(uri):
    """白底黑色SVG保持方形比例，手动添加资料只出现在这份临时文件中。"""
    otp = pyotp.parse_uri(uri)
    code = qrcode.QRCode(border=4)
    code.add_data(uri)
    code.make(fit=True)
    picture = code.make_image(image_factory=SvgPathFillImage).to_string(encoding="unicode")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>BUMBUM 验证器设置</title>
<style>
html {{ color-scheme: only light; background: #fff; color: #111; font: 18px/1.7 system-ui, sans-serif; }}
main {{ max-width: 640px; margin: 24px auto; padding: 24px; }}
svg {{ display: block; width: min(440px, 100%); height: auto; margin: 24px auto; background: #fff; }}
code {{ display: block; padding: 12px; background: #f4f4f4; overflow-wrap: anywhere; user-select: all; }}
summary {{ cursor: pointer; }}
</style>
</head>
<body><main>
<h1>添加手机 Authenticator</h1>
<p>账号：{escape(otp.issuer or '')} / {escape(otp.name)}</p>
<p>在 Authenticator 中选择“添加账号 → 扫描二维码”。</p>
{picture}
<p>扫码后回到终端，输入手机当前6位验证码，完成确认。</p>
<details><summary>仍无法扫码？手动添加账号</summary>
<p>在 Authenticator 中选择手动输入，账号名填写上面的账号，密钥填写：</p>
<code>{escape(otp.secret)}</code>
<p>类型选择“基于时间”；如需填写参数，使用6位数字、30秒、SHA1。</p>
</details>
<p>这是本机临时设置页面，请勿截图或分享。完成或取消后关闭此页面。</p>
</main></body></html>"""


@contextmanager
def show_qr(uri):
    """只打开本机文件；确认、失败或Ctrl+C后清理临时文件。"""
    try:
        with TemporaryDirectory(prefix="bumbum-authenticator-") as folder:
            path = Path(folder) / "authenticator.html"
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(setup_page(uri))
            click.echo(f"验证器设置页面已在本机生成：{path}")
            desktop = os.name == "nt" or sys.platform == "darwin" or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
            opened = False
            if desktop:
                try:
                    opened = webbrowser.open(path.as_uri(), new=2)
                except (webbrowser.Error, OSError):
                    pass
            if not opened:
                click.echo("未能自动打开浏览器，请在运行此命令的电脑上打开上述文件。")
            click.echo("请扫描页面中的二维码；若仍无法识别，展开页面的“手动添加账号”。")
            yield path
    except OSError:
        raise click.ClickException("临时设置页面无法生成或清理，请关闭页面并检查系统临时目录权限后重试。") from None
