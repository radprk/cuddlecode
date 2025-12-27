from __future__ import annotations

import logging
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _run_git(args: list[str], cwd: Optional[Path] = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _extract_repo_name(repo_url: str) -> str:
    if repo_url.startswith("git@"):  # git@github.com:user/repo.git
        path = repo_url.split(":", 1)[-1]
    else:
        path = repo_url.rstrip("/")
        if "://" in path:
            path = path.split("://", 1)[-1]
        path = path.split("/", 1)[-1]
    name = Path(path).name
    if name.endswith(".git"):
        name = name[: -len(".git")]
    return name


def clone_repo(repo_url: str, branch: Optional[str] = None, commit_sha: Optional[str] = None) -> Path:
    """Clone a repo into repos/<repo_name>/<commit_sha> and return the local path."""
    repo_name = _extract_repo_name(repo_url)
    base_dir = Path("repos") / repo_name
    base_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = base_dir / f".tmp-{uuid.uuid4().hex}"
    clone_args = ["clone", repo_url, str(temp_dir)]
    if branch:
        clone_args.extend(["--branch", branch, "--single-branch"])
    logger.info("Cloning %s into %s", repo_url, temp_dir)
    _run_git(clone_args)

    if commit_sha:
        logger.info("Checking out commit %s", commit_sha)
        _run_git(["checkout", commit_sha], cwd=temp_dir)

    resolved_sha = _run_git(["rev-parse", "HEAD"], cwd=temp_dir)
    target_dir = base_dir / resolved_sha
    if target_dir.exists():
        shutil.rmtree(temp_dir)
        raise FileExistsError(f"Target repo directory already exists: {target_dir}")
    logger.info("Moving repo to %s", target_dir)
    shutil.move(str(temp_dir), str(target_dir))
    print(f"Cloned repo to: {target_dir}")
    return target_dir
