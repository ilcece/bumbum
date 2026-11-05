"""把实际Umi产物导出为离线单HTML，同时打包不含依赖/生成目录的源码。"""
from pathlib import Path
import argparse,base64,re,zipfile
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[1];dist=root/'dist';out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
page=(dist/'index.html').read_text()
# Umi仍使用真实拆包运行时；预先注册路由块，避免离线时动态请求外部文件。
entry=re.findall(r'<script[^>]+src="([^"]+)"[^>]*></script>',page)
entry_names={Path(s).name for s in entry}
def script(p):return '<script>'+p.read_text().replace('</script','<\\/script')+'</script>'
chunks=''.join(script(p) for p in sorted(dist.glob('*.js')) if p.name not in entry_names)
styles=''
for p in sorted(dist.glob('*.css')):
 styles+='<style data-href="./'+p.name+'">'+p.read_text()+'</style><style data-href="'+p.name+'"></style>'
page=re.sub(r'<link[^>]+rel="stylesheet"[^>]*>','',page)
# 预加载助手只用于多文件部署；单文件已包含所有块，不运行额外预取。
page=re.sub(r'<script[^>]+src="([^"]+)"[^>]*></script>',lambda m:'' if Path(m.group(1)).name.startswith('preload_helper.') else script(dist/Path(m.group(1)).name),page)
page=page.replace('</head>',styles+'</head>').replace('<div id="root"></div>','<div id="root"></div>'+chunks)
icon='data:image/svg+xml;base64,'+base64.b64encode((dist/'favicon.svg').read_bytes()).decode()
page=page.replace('href="./favicon.svg"','href="'+icon+'"')
html_path=out/'管理后台高保真交互原型.html';html_path.write_text(page);(root/'preview.html').write_text(page)
excluded={'node_modules','dist','.git','__pycache__','.pytest_cache','.cache'}
archive=out/'管理后台高保真原型-源码.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(root.rglob('*')):
  rel=p.relative_to(root)
  if any(part in excluded or part.startswith('.umi') for part in rel.parts) or p.suffix=='.log':continue
  if p.is_symlink():raise ValueError('源码包不能包含符号链接：'+str(rel))
  if p.is_file():
   if p.name=='.env' or p.name.startswith('.env.'):raise ValueError('不得打包环境凭据')
   z.write(p,str(rel))
print('已导出真实Umi单文件及源码包，HTML字节：',html_path.stat().st_size)
print(html_path);print(archive)
