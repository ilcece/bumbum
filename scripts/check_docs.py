"""检查仓库Markdown的本地链接、标题定位、JSON示例和代码框。"""

from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def inspect_markdown(path):
    """跳过代码框里的示例链接；逐个检查JSON，不读取本机秘密配置。"""
    errors, plain, block = [], [], []
    fence, language, opening = None, "", 0
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if fence is None:
            match = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
            if match:
                fence, language, opening = match[1], match[2].strip(), number
                block = []
            else:
                plain.append((number, line))
        elif re.fullmatch(r"\s*" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
            if language == "json":
                try:
                    json.loads("\n".join(block))
                except ValueError:
                    errors.append(f"第{opening}行的JSON示例无法解析")
            fence = None
        else:
            block.append(line)
    if fence:
        errors.append(f"第{opening}行的代码框没有结束")
    anchors, seen = set(), Counter()
    for _number, line in plain:
        anchors.update(re.findall(r'<a\s+(?:name|id)=["\x27]([^"\x27]+)["\x27]\s*>', line))
        heading = re.match(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", line)
        if heading:
            slug = re.sub(r"[^\w\- ]", "", heading[1].lower().replace("`", "")).replace(" ", "-")
            anchors.add(slug if not seen[slug] else f"{slug}-{seen[slug]}")
            seen[slug] += 1
    return plain, anchors, errors


def check_docs(root=ROOT):
    root = root.resolve()
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "*.md"], cwd=root, capture_output=True)
    if result.returncode:
        return ["无法列出Git工作区文档，请在完整仓库中运行。"], 0, 0
    names = sorted(set(result.stdout.decode("utf-8").strip("\0").split("\0")) - {""})
    documents, errors = {}, []
    for name in names:
        source = root / name
        if source.is_symlink():
            errors.append(f"{name}：文档不能通过符号链接读取")
            continue
        path = source.resolve()
        if not path.is_relative_to(root):
            errors.append(f"{name}：文档路径越出仓库范围")
            continue
        if not path.is_file():
            continue
        try:
            documents[path] = inspect_markdown(path)
        except UnicodeError:
            errors.append(f"{name}：请将文档保存为UTF-8")
        except OSError:
            errors.append(f"{name}：无法读取，请检查文件权限")
    if not documents:
        errors.append("没有可检查的Markdown文档。")
    links = 0
    for path, (plain, _anchors, problems) in documents.items():
        name = path.relative_to(root.resolve())
        errors.extend(f"{name}：{problem}" for problem in problems)
        for number, line in plain:
            if re.match(r"^(?:<{7}(?:\s|$)|={7}$|>{7}(?:\s|$))", line):
                errors.append(f"{name}:{number}：存在未解决的Git合并标记")
            if str(name) == "README.md" and re.search(r"(?:本|当前)分支.*(?:待验收|未合入\s*main|未合并)|(?<![A-Za-z0-9_])(?:feat|fix)/[A-Za-z0-9_-]+", line):
                errors.append(f"{name}:{number}：临时任务分支状态应维护在TODO，历史版本应放CHANGELOG")
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", line):
                parsed = urlsplit(target.strip().strip("<>"))
                if parsed.scheme or parsed.netloc:
                    continue
                destination = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
                links += 1
                if not destination.is_relative_to(root):
                    errors.append(f"{name}:{number}：链接目标越出仓库范围：{target}")
                elif not destination.exists():
                    errors.append(f"{name}:{number}：链接目标不存在：{target}")
                elif parsed.fragment:
                    fragment = unquote(parsed.fragment)
                    if destination not in documents or fragment not in documents[destination][1]:
                        errors.append(f"{name}:{number}：标题定位不存在：{target}")
    return errors, len(documents), links


def main():
    errors, count, links = check_docs()
    if errors:
        for error in errors:
            print("未通过：" + error)
        return 1
    print(f"通过：{count}份文档、{links}个本地链接及标题定位；JSON/代码框、合并标记和README临时状态检查通过。")
    print("仍需人工核对文档与代码、分支和验收状态是否一致；未检查外部网址可访问性。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
