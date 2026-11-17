"""用真实临时 Git 历史验证 CI 范围、保守分流和提交差异检查。"""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.ci_scope import ZERO_SHA, check_diff, classify


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci_scope.py"


class Repository:
    def __init__(self, path):
        self.path = path
        path.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "CI scope test")
        self.git("config", "user.email", "ci-scope@example.invalid")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.path, capture_output=True, text=True, check=True,
                              env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()

    def commit(self, changes):
        for name, content in changes.items():
            target = self.path / name
            if content is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        self.git("add", "--all")
        self.git("commit", "-qm", "isolated change")
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    repository = Repository(tmp_path / "repo")
    repository.base = repository.commit({"README.md": "# Existing documentation\n", "app.py": "ready = True\n"})
    return repository


def push(base, head):
    return {"ref": "refs/heads/main", "before": base, "after": head}


def pull(base, head):
    return {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}


def run_script(repo, tmp_path, event, payload):
    event_path, output = tmp_path / "event.json", tmp_path / "output"
    event_path.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo.path)], capture_output=True, text=True,
                            env={**os.environ, "GITHUB_EVENT_NAME": event, "GITHUB_EVENT_PATH": str(event_path),
                                 "GITHUB_OUTPUT": str(output), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    return result, output.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", [
    "README.md", "PRODUCT.md", "PRD.md", "TECH_SPEC.md", "API_CONTRACT.md",
    "AGENTS.md", "TODO.md", "CHANGELOG.md", "docs/guide.md", "docs/product/deep/guide.md",
])
def test_only_explicit_document_paths_are_lightweight(repo, name):
    head = repo.commit({name: "# Changed documentation\n"})
    scope = classify(repo.path, "pull_request", pull(repo.base, head))
    assert not scope.full and not scope.error
    assert scope.paths == (name,)
    check_diff(repo.path, scope)


def test_deleted_document_is_still_part_of_the_range(repo):
    head = repo.commit({"README.md": None})
    scope = classify(repo.path, "push", push(repo.base, head))
    assert not scope.full and scope.paths == ("README.md",)


@pytest.mark.parametrize("old,new", [
    ("README.md", "core/README.md"),
    ("app.py", "docs/implementation.md"),
])
def test_rename_keeps_both_old_and_new_paths(repo, old, new):
    content = (repo.path / old).read_text()
    head = repo.commit({old: None, new: content})
    scope = classify(repo.path, "pull_request", pull(repo.base, head))
    assert scope.full and not scope.error
    assert set(scope.paths) == {old, new}


@pytest.mark.parametrize("name", [
    "app.py", ".github/workflows/checks.yml", ".agents/skills/rules/SKILL.md",
    "prototypes/README.md", "CONTRIBUTING.md", "docs/check.py",
])
def test_source_ci_and_markdown_outside_allowlist_keep_full_checks(repo, name):
    head = repo.commit({"README.md": "# Updated\n", name: "changed = True\n"})
    scope = classify(repo.path, "push", push(repo.base, head))
    assert scope.full and not scope.error


def test_pr_uses_merge_base_instead_of_adding_new_base_changes(repo):
    repo.git("checkout", "-qb", "proposal")
    head = repo.commit({"docs/change.md": "# Proposal\n"})
    repo.git("checkout", "-q", "main")
    current_base = repo.commit({"app.py": "ready = False\n"})
    scope = classify(repo.path, "pull_request", pull(current_base, head))
    assert not scope.full and not scope.error
    assert scope.base == repo.base and scope.head == head
    assert scope.paths == ("docs/change.md",)


def test_push_checks_all_pushed_commits_not_only_head_parent(repo):
    repo.commit({"app.py": "ready = False\n"})
    head = repo.commit({"README.md": "# Last commit only changes docs\n"})
    scope = classify(repo.path, "push", push(repo.base, head))
    assert scope.full and scope.base == repo.base and scope.head == head
    assert set(scope.paths) == {"app.py", "README.md"}


@pytest.mark.parametrize("event", ["workflow_dispatch", "unknown", "pull_request_target"])
def test_events_without_a_defined_change_range_are_full_and_explicitly_last_commit(repo, event):
    head = repo.commit({"README.md": "# Documentation\n"})
    scope = classify(repo.path, event, {})
    assert scope.full and not scope.error
    assert scope.base == repo.base and scope.head == head
    assert "最后一次提交" in scope.reason
    check_diff(repo.path, scope)


def test_manual_root_commit_uses_empty_tree(tmp_path):
    repo = Repository(tmp_path / "root")
    head = repo.commit({"README.md": "# First commit\n"})
    scope = classify(repo.path, "workflow_dispatch", {})
    assert scope.full and not scope.error and scope.head == head
    assert repo.git("cat-file", "-t", scope.base) == "tree"
    check_diff(repo.path, scope)


def test_first_main_push_is_full_even_when_every_file_is_documentation(tmp_path):
    repo = Repository(tmp_path / "first")
    head = repo.commit({"README.md": "# First push\n"})
    scope = classify(repo.path, "push", push(ZERO_SHA, head))
    assert scope.full and not scope.error and scope.paths == ("README.md",)
    assert repo.git("cat-file", "-t", scope.base) == "tree"
    check_diff(repo.path, scope)


def test_missing_baseline_is_full_but_does_not_claim_a_replacement_range(repo, tmp_path):
    payload = push("a" * 40, repo.base)
    scope = classify(repo.path, "push", payload)
    assert scope.full and scope.error and scope.base is None
    with pytest.raises(ValueError):
        check_diff(repo.path, scope)
    result, output = run_script(repo, tmp_path, "push", payload)
    assert result.returncode != 0 and output == "full=true\n"
    assert "缺少准确差异范围" in result.stderr


@pytest.mark.parametrize("event,payload", [
    ("push", {"ref": "refs/heads/main", "before": ZERO_SHA}),
    ("push", {"ref": "refs/heads/main", "before": "$(touch unexpected)", "after": "a" * 40}),
    ("pull_request", {"pull_request": {"base": {"sha": ZERO_SHA}, "head": {"sha": "a" * 40}}}),
    ("pull_request", {"pull_request": []}),
])
def test_bad_normal_event_payload_is_not_treated_as_unknown_event(repo, event, payload):
    scope = classify(repo.path, event, payload)
    assert scope.full and scope.error
    assert scope.base is None and scope.head is None
    assert not (repo.path / "unexpected").exists()


def test_unrelated_pr_histories_fail_instead_of_guessing_a_range(repo):
    repo.git("checkout", "--orphan", "unrelated")
    repo.git("rm", "-qrf", ".")
    head = repo.commit({"docs/unrelated.md": "# Unrelated root\n"})
    scope = classify(repo.path, "pull_request", pull(repo.base, head))
    assert scope.full and scope.error


def test_empty_difference_is_conservatively_full(repo):
    scope = classify(repo.path, "push", push(repo.base, repo.base))
    assert scope.full and not scope.error and not scope.paths
    check_diff(repo.path, scope)


def test_document_whitespace_failure_makes_cli_fail_even_when_lightweight(repo, tmp_path):
    head = repo.commit({"README.md": "# Trailing whitespace  \n"})
    result, output = run_script(repo, tmp_path, "push", push(repo.base, head))
    assert output == "full=false\n"
    assert result.returncode != 0
    assert "README.md" in result.stderr


def test_cli_reads_event_file_and_emits_the_lightweight_output(repo, tmp_path):
    head = repo.commit({"docs/update.md": "# Documentation\n"})
    result, output = run_script(repo, tmp_path, "pull_request", pull(repo.base, head))
    assert result.returncode == 0 and output == "full=false\n"


def test_shallow_checkout_can_fetch_the_exact_missing_push_sha_from_origin(repo, tmp_path):
    head = repo.commit({"README.md": "# Latest documentation\n"})
    clone = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth=1", repo.path.as_uri(), str(clone)], check=True)
    missing = subprocess.run(["git", "cat-file", "-e", repo.base], cwd=clone, capture_output=True)
    assert missing.returncode != 0
    scope = classify(clone, "push", push(repo.base, head), fetch_missing=True)
    assert not scope.full and not scope.error
    assert scope.base == repo.base and scope.head == head
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=clone, text=True).strip() == head
    check_diff(clone, scope)
