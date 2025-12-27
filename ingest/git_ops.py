from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloneResult:
    repo_dir: Path
    repo_name: str
    commit_sha: str


def extract_repo_name(repo_url: str) -> str:
    trimmed = repo_url.rstrip("/")
    if trimmed.endswith(".git"):
        trimmed = trimmed[: -len(".git")]
    if ":" in trimmed and "@" in trimmed:
        trimmed = trimmed.split(":", 1)[-1]
    return trimmed.split("/")[-1]


def resolve_commit_sha(repo_url: str, branch: str | None, commit_sha: str | None) -> str:
    if commit_sha:
        return commit_sha
    target = branch or "HEAD"
    result = subprocess.run(
        ["git", "ls-remote", repo_url, target],
        check=True,
        capture_output=True,
        text=True,
    )
    sha = result.stdout.strip().split()[0]
    if not sha:
        raise RuntimeError(f"Unable to resolve commit for {repo_url} {target}")
    return sha


def clone_repo(
    repo_url: str,
    base_dir: Path = Path("./repos"),
    branch: str | None = None,
    commit_sha: str | None = None,
) -> CloneResult:
    repo_name = extract_repo_name(repo_url)
    resolved_sha = resolve_commit_sha(repo_url, branch, commit_sha)
    target_dir = base_dir / repo_name / resolved_sha
    if target_dir.exists():
        LOGGER.info("Repo already cloned at %s", target_dir)
        return CloneResult(repo_dir=target_dir, repo_name=repo_name, commit_sha=resolved_sha)

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Cloning %s into %s", repo_url, target_dir)
    subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True)
    subprocess.run(["git", "-C", str(target_dir), "checkout", resolved_sha], check=True)
    return CloneResult(repo_dir=target_dir, repo_name=repo_name, commit_sha=resolved_sha)
