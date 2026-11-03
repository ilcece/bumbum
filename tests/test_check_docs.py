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


def add_managed_doc(root, name, metadata, body="", indexed=True):
    """在独立小仓库构造文档，不读取项目秘密或运行业务服务。"""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + metadata + "\n---\n\n# 文档\n\n" + body, encoding="utf-8")
    if indexed:
        index = root / "PRD.md"
        previous = index.read_text(encoding="utf-8") if index.exists() else "# 产品入口\n\n"
        index.write_text(previous + f"[文档]({name})\n", encoding="utf-8")


def test_current_rules_and_approved_proposal_have_distinct_places(docs_repo):
    add_managed_doc(docs_repo, "docs/product/items.md", "doc_type: product\nstatus: approved")
    add_managed_doc(docs_repo, "docs/proposals/cleanup.md", "doc_type: proposal\nstatus: approved")
    assert check_docs.check_docs(docs_repo)[0] == []


def test_archive_without_replacement_is_valid(docs_repo):
    add_managed_doc(docs_repo, "docs/archive/old.md", "doc_type: archive\nstatus: archived\ndate: 2026-11-03\nreason: 方向停止，不存在替代方案。")
    assert check_docs.check_docs(docs_repo)[0] == []


@pytest.mark.parametrize("name, metadata, expected", [
    ("docs/product/items.md", "doc_type: product\nstatus: archived", "status不适合"),
    ("docs/proposals/cleanup.md", "doc_type: product\nstatus: review", "doc_type应为proposal"),
    ("docs/archive/old.md", "doc_type: archive\nstatus: approved", "status不适合"),
    ("docs/archive/old.md", "doc_type: archive\nstatus: archived\ndate: 2026-11-03", "缺少非空reason"),
    ("docs/archive/old.md", "doc_type: archive\nstatus: archived\ndate: 2026-02-30\nreason: 被取代", "有效的YYYY-MM-DD"),
    ("docs/archive/old.md", "doc_type: archive\nstatus: archived\ndate: 2026-11-03\nreason: 被取代\nsuperseded_by: missing.md", "superseded_by须指向"),
    ("docs/product/items.md", "doc_type: product\nstatus: approved\nstatus: review", "元数据重复"),
])
def test_governance_errors_are_blocked(docs_repo, name, metadata, expected):
    add_managed_doc(docs_repo, name, metadata)
    assert any(expected in error for error in check_docs.check_docs(docs_repo)[0])


def test_proposal_can_be_reached_through_module_navigation(docs_repo):
    add_managed_doc(docs_repo, "docs/product/items.md", "doc_type: product\nstatus: approved", "[清理](../proposals/cleanup.md)")
    add_managed_doc(docs_repo, "docs/proposals/cleanup.md", "doc_type: proposal\nstatus: review", indexed=False)
    assert check_docs.check_docs(docs_repo)[0] == []


def test_historical_link_does_not_replace_product_navigation(docs_repo):
    add_managed_doc(docs_repo, "docs/proposals/cleanup.md", "doc_type: proposal\nstatus: review", indexed=False)
    (docs_repo / "PRD.md").write_text("# 产品入口\n", encoding="utf-8")
    (docs_repo / "CHANGELOG.md").write_text("[旧链接](docs/proposals/cleanup.md)\n", encoding="utf-8")
    assert any("产品入口无法到达" in error for error in check_docs.check_docs(docs_repo)[0])


def test_missing_product_index_is_blocked(docs_repo):
    add_managed_doc(docs_repo, "docs/product/items.md", "doc_type: product\nstatus: approved", indexed=False)
    assert any("缺少产品入口PRD.md" in error for error in check_docs.check_docs(docs_repo)[0])


def test_missing_governance_metadata_is_blocked(docs_repo):
    add_managed_doc(docs_repo, "docs/product/items.md", "doc_type: product\nstatus: approved")
    (docs_repo / "docs/product/items.md").write_text("# 遗漏元数据\n", encoding="utf-8")
    assert any("缺少开头的元数据" in error for error in check_docs.check_docs(docs_repo)[0])


def test_replacement_path_and_anchor_are_checked(docs_repo):
    add_managed_doc(docs_repo, "docs/product/items.md", "doc_type: product\nstatus: approved")
    add_managed_doc(docs_repo, "docs/archive/old.md", "doc_type: archive\nstatus: archived\ndate: 2026-11-03\nreason: 被取代\nsuperseded_by: ../product/items.md#文档")
    assert check_docs.check_docs(docs_repo)[0] == []
    path = docs_repo / "docs/archive/old.md"
    path.write_text(path.read_text(encoding="utf-8").replace("#文档", "#不存在"), encoding="utf-8")
    assert any("superseded_by的标题定位不存在" in error for error in check_docs.check_docs(docs_repo)[0])
