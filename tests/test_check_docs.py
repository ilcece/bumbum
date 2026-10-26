"""验证文档检查能保留旧入口并发现明确的维护错误。"""

import importlib.util
from pathlib import Path
import subprocess

import pytest


_spec = importlib.util.spec_from_file_location("check_docs", Path(__file__).resolve().parents[1] / "scripts/check_docs.py")
check_docs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_docs)


@pytest.fixture
def docs_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "README.md").write_text("# 项目\n", encoding="utf-8")
    return tmp_path


def test_preserved_alias(docs_repo):
    (docs_repo / "A.md").write_text('<a name="旧入口"></a>\n\n## 新标题\n', encoding="utf-8")
    (docs_repo / "README.md").write_text("[旧链接](A.md#旧入口)\n", encoding="utf-8")
    errors, count, links = check_docs.check_docs(docs_repo)
    assert errors == []
    assert (count, links) == (2, 1)


@pytest.mark.parametrize("content, expected", [
    ("[坏链接](missing.md)", "链接目标不存在"),
    ("<<<<<<< HEAD\n冲突\n=======\n内容\n>>>>>>> task", "合并标记"),
    ("当前分支待验收", "临时任务分支状态"),
    ("本次来自feat/example", "临时任务分支状态"),
])
def test_maintenance_errors(docs_repo, content, expected):
    (docs_repo / "README.md").write_text(content, encoding="utf-8")
    assert any(expected in error for error in check_docs.check_docs(docs_repo)[0])


def test_historical_and_code_examples_allowed(docs_repo):
    (docs_repo / "CHANGELOG.md").write_text("当前分支待验收：feat/example\n", encoding="utf-8")
    (docs_repo / "README.md").write_text("```text\n<<<<<<< HEAD\n当前分支待验收\n```\n", encoding="utf-8")
    assert check_docs.check_docs(docs_repo)[0] == []
