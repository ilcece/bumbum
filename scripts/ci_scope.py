"""按事件的已提交差异分流 CI；无法证明纯文档时保留完整检查。"""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


DOCUMENTS = frozenset({
    "README.md", "PRODUCT.md", "PRD.md", "TECH_SPEC.md", "API_CONTRACT.md",
    "AGENTS.md", "TODO.md", "CHANGELOG.md",
})
ZERO_SHA = "0" * 40


@dataclass(frozen=True)
class Scope:
    full: bool
    reason: str
    base: str | None = None
    head: str | None = None
    paths: tuple[str, ...] = ()
    error: bool = False


def git(repo, *args, input=None):
    return subprocess.run(["git", *args], cwd=repo, input=input, capture_output=True,
                          check=True, timeout=30).stdout


def commit_sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", value) or value == ZERO_SHA:
        raise ValueError("缺少准确提交号")
    return value.lower()


def ensure_commit(repo, sha, fetch_missing):
    try:
        git(repo, "cat-file", "-e", sha + "^{commit}")
    except subprocess.CalledProcessError:
        if not fetch_missing:
            raise
        # 只向 checkout 配置的本仓库 origin 取准确 SHA，不采用事件提供的仓库或 ref。
        git(repo, "fetch", "--no-tags", "--no-recurse-submodules", "origin", sha)
        git(repo, "cat-file", "-e", sha + "^{commit}")


def empty_tree(repo):
    return git(repo, "hash-object", "-w", "-t", "tree", "--stdin", input=b"").decode().strip()


def is_document(path):
    parts = PurePosixPath(path).parts
    return path in DOCUMENTS or (
        len(parts) >= 2 and parts[0] == "docs" and path.endswith(".md")
        and not any(part in {".", ".."} for part in parts)
    )


def last_commit(repo, fetch_missing):
    head = commit_sha(git(repo, "rev-parse", "--verify", "HEAD").decode().strip())
    headers = git(repo, "cat-file", "-p", head).split(b"\n\n", 1)[0].splitlines()
    parents = [line[7:].decode() for line in headers if line.startswith(b"parent ")]
    if parents:
        base = commit_sha(parents[0])
        ensure_commit(repo, base, fetch_missing)
    else:
        base = empty_tree(repo)
    return Scope(True, "手动或未知事件：执行完整检查；差异检查仅覆盖最后一次提交。", base, head)


def classify(repo, event_name, payload, *, fetch_missing=False):
    try:
        if event_name not in {"pull_request", "push"}:
            return last_commit(repo, fetch_missing)
        if not isinstance(payload, dict):
            raise ValueError("事件内容不可读取")
        first_push = False
        if event_name == "pull_request":
            pull = payload.get("pull_request")
            if not isinstance(pull, dict) or not isinstance(pull.get("base"), dict) or not isinstance(pull.get("head"), dict):
                raise ValueError("PR 提交范围不完整")
            base, head = commit_sha(pull["base"].get("sha")), commit_sha(pull["head"].get("sha"))
        else:
            if payload.get("ref") != "refs/heads/main":
                raise ValueError("不是已知的 main push")
            head = commit_sha(payload.get("after"))
            first_push = payload.get("before") == ZERO_SHA
            base = empty_tree(repo) if first_push else commit_sha(payload.get("before"))
        ensure_commit(repo, head, fetch_missing)
        if not first_push:
            ensure_commit(repo, base, fetch_missing)
        if event_name == "pull_request":
            base = commit_sha(git(repo, "merge-base", base, head).decode().strip())
        changed = git(repo, "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                      "--name-only", "-z", base, head, "--")
        paths = tuple(path.decode("utf-8") for path in changed.split(b"\0") if path)
        if first_push:
            return Scope(True, "首次 main push：从空树检查全部提交文件，执行完整检查。", base, head, paths)
        if not paths:
            return Scope(True, "没有可分类的提交差异，执行完整检查。", base, head)
        full = not all(is_document(path) for path in paths)
        return Scope(full, "含源码或白名单外文件，执行完整检查。" if full else "仅文档白名单内变更，省略源码检查。",
                     base, head, paths)
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return Scope(True, "无法取得准确的已提交差异范围；按完整范围分类，但本次基础检查必须失败。", error=True)


def check_diff(repo, scope):
    if scope.error or not scope.base or not scope.head:
        raise ValueError("缺少准确差异范围，未执行替代范围检查")
    git(repo, "diff", "--check", "--no-ext-diff", "--no-textconv", "--no-renames",
        scope.base, scope.head, "--")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--event-name", default=os.getenv("GITHUB_EVENT_NAME", ""))
    parser.add_argument("--event-path", type=Path, default=os.getenv("GITHUB_EVENT_PATH"))
    parser.add_argument("--github-output", type=Path, default=os.getenv("GITHUB_OUTPUT"))
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.event_path.read_text(encoding="utf-8")) if args.event_path else None
    except (OSError, ValueError):
        payload = None
    scope = classify(args.repo, args.event_name, payload, fetch_missing=True)
    output = f"full={'true' if scope.full else 'false'}\n"
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(output)
    print(output.strip())
    print(scope.reason)
    try:
        check_diff(args.repo, scope)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        if isinstance(error, subprocess.CalledProcessError):
            for text in (error.stdout, error.stderr):
                if text:
                    print(text.decode("utf-8", errors="replace"), file=sys.stderr, end="")
        print("已提交差异检查失败。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
