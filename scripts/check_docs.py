"""检查仓库Markdown的本地链接、标题定位、JSON示例和代码框。"""

from collections import Counter
from datetime import date
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


def inspect_metadata(path):
    """只读取治理目录采用的单行元数据，不推断审批或业务事实。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}, ["治理文档缺少开头的元数据"]
    metadata, errors = {}, []
    for line in lines[1:]:
        if line == "---":
            return metadata, errors
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([a-z_]+):\s*(.*?)\s*", line)
        if not match or match[2].startswith(("|", ">")):
            errors.append("治理元数据须使用单行key: value")
            continue
        key, value = match[1], match[2].strip().strip("\"'")
        if key in metadata:
            errors.append(f"治理元数据重复：{key}")
        metadata[key] = value
    return metadata, errors + ["治理元数据缺少结束分隔线"]


def check_governance(root, documents, graph):
    """检查确定性元数据与产品入口，不以关键词替代人工语义审查。"""
    managed, errors = {}, []
    categories = {"product": {"approved"}, "proposals": {"draft", "review", "approved"}, "archive": {"archived"}}
    for path in documents:
        parts = path.relative_to(root).parts
        if len(parts) >= 3 and parts[0] == "docs" and parts[1] in categories:
            managed[path] = parts[1]
    for path, category in managed.items():
        name = path.relative_to(root)
        metadata, problems = inspect_metadata(path)
        errors.extend(f"{name}：{problem}" for problem in problems)
        expected_type = "proposal" if category == "proposals" else category
        if metadata.get("doc_type") != expected_type:
            errors.append(f"{name}：doc_type应为{expected_type}")
        if metadata.get("status") not in categories[category]:
            errors.append(f"{name}：status不适合当前目录{category}")
        if category != "archive":
            continue
        if metadata.get("reason", "").strip().lower() in {"", "null", "~"}:
            errors.append(f"{name}：归档缺少非空reason")
        stamp = metadata.get("date", "")
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", stamp):
                raise ValueError
            date.fromisoformat(stamp)
        except ValueError:
            errors.append(f"{name}：归档date须为有效的YYYY-MM-DD日期")
        replacement = metadata.get("superseded_by")
        if replacement:
            parsed = urlsplit(replacement)
            target = (path.parent / unquote(parsed.path)).resolve()
            if parsed.scheme or parsed.netloc or not parsed.path or not target.is_relative_to(root) or target not in documents:
                errors.append(f"{name}：superseded_by须指向仓库内存在的相对文档")
            elif parsed.fragment and unquote(parsed.fragment) not in documents[target][1]:
                errors.append(f"{name}：superseded_by的标题定位不存在")
    active = {path for path, category in managed.items() if category != "archive"}
    if active:
        index = root / "PRD.md"
        if index not in documents:
            errors.append("治理目录存在产品规范或提案，但缺少产品入口PRD.md")
        else:
            # 只沿产品入口及治理文档查找，历史CHANGELOG中的链接不替代现行入口。
            allowed = set(managed) | {index}
            visited, pending = set(), [index]
            while pending:
                current = pending.pop()
                if current in visited:
                    continue
                visited.add(current)
                pending.extend((graph.get(current, set()) & allowed) - visited)
            for path in sorted(active - visited):
                errors.append(f"{path.relative_to(root)}：产品入口无法到达，请在PRD或其治理文档中补充导航")
    return errors


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
    links, graph = 0, {}
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
                else:
                    graph.setdefault(path, set()).add(destination)
                    if parsed.fragment:
                        fragment = unquote(parsed.fragment)
                        if destination not in documents or fragment not in documents[destination][1]:
                            errors.append(f"{name}:{number}：标题定位不存在：{target}")
    errors.extend(check_governance(root, documents, graph))
    return errors, len(documents), links


def main():
    errors, count, links = check_docs()
    if errors:
        for error in errors:
            print("未通过：" + error)
        return 1
    print(f"通过：{count}份文档、{links}个本地链接及标题定位；JSON/代码框、合并标记、README临时状态、治理元数据/归档和产品入口检查通过。")
    print("仍需人工核对文档与代码、分支和验收状态是否一致；未检查外部网址可访问性。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
