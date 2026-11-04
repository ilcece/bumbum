"""导出可离线打开的单HTML及不含依赖、缓存和秘密的原型源码包。"""
from pathlib import Path
import argparse,base64,re,zipfile
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[1];out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
page=(root/'dist/index.html').read_text()
def asset(src):
 p=(root/'dist'/src.lstrip('./')).resolve()
 if not p.is_relative_to(root/'dist'):raise ValueError('资源路径越界')
 return p.read_text()
page=re.sub(r'<script type="module"[^>]*src="([^"]+)"[^>]*></script>',lambda m:'<script type="module">'+asset(m.group(1)).replace('</script','<\\/script')+'</script>',page)
page=re.sub(r'<link rel="stylesheet"[^>]*href="([^"]+)"[^>]*>',lambda m:'<style>'+asset(m.group(1))+'</style>',page)
icon='data:image/svg+xml;base64,'+base64.b64encode((root/'public/favicon.svg').read_bytes()).decode()
page=re.sub(r'href="\./favicon.svg"',lambda m:'href="'+icon+'"',page)
html_path=out/'管理后台高保真交互原型.html';html_path.write_text(page)
(root/'preview.html').write_text(page)
excluded={'node_modules','dist','.git','__pycache__','.pytest_cache','.cache'}
archive=out/'管理后台高保真原型-源码.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(root.rglob('*')):
  rel=p.relative_to(root)
  if any(part in excluded for part in rel.parts) or p.suffix=='.log':continue
  if p.is_symlink():raise ValueError('源码包不能包含符号链接：'+str(rel))
  if p.is_file():
   if p.name=='.env' or p.name.startswith('.env.'):raise ValueError('不得打包环境凭据')
   z.write(p,str(rel))
with zipfile.ZipFile(archive) as z:
 for name in ['install','dev','deploy-preview','deploy']:
  entry=z.getinfo('.figma/make/'+name)
  if not ((entry.external_attr>>16)&0o111):raise ValueError('生命周期脚本缺少执行权限')
 print('导出完成：单HTML、源码ZIP；归档',len(z.namelist()),'个文件，无依赖目录或链接。')
print(html_path);print(archive)
