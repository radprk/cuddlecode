from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Optional

from ingest.chunking import chunk_text
from ingest.constants import DEFAULT_IGNORE_PATTERNS, LANGUAGE_BY_EXTENSION
from ingest.ignore import filter_ignored_dirs, should_ignore
from ingest.python_ast import extract_imports

logger = logging.getLogger(__name__)


class RepoIndexError(RuntimeError):
    pass


def _git_head_sha(repo_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RepoIndexError("Unable to resolve HEAD SHA") from exc
    return result.stdout.strip()


def _git_remote_name(repo_dir: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "config", "--get", "remote.origin.url"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    url = result.stdout.strip()
    if not url:
        return None
    if url.startswith("git@"):  # git@github.com:user/repo.git
        path = url.split(":", 1)[-1]
    else:
        path = url.rstrip("/")
        if "://" in path:
            path = path.split("://", 1)[-1]
        path = path.split("/", 1)[-1]
    name = Path(path).name
    if name.endswith(".git"):
        name = name[: -len(".git")]
    return name


def _is_text_file(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except OSError:
        return False
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _sha256_bytes(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def _language_for_path(path: Path) -> str:
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "unknown")


def index_repo(repo_dir: Path, ignore_patterns: Optional[Iterable[str]] = None) -> Path:
    """Index a local repo into JSONL manifests, units, and import graph."""
    repo_dir = repo_dir.resolve()
    if ignore_patterns is None:
        ignore_patterns = DEFAULT_IGNORE_PATTERNS

    repo_name = _git_remote_name(repo_dir) or repo_dir.name
    commit_sha = _git_head_sha(repo_dir)
    output_dir = Path("indexes") / repo_name / commit_sha
    output_dir.mkdir(parents=True, exist_ok=True)
    files_path = output_dir / "files.jsonl"
    units_path = output_dir / "units.jsonl"
    imports_path = output_dir / "imports.jsonl"

    logger.info("Indexing repo %s at %s", repo_name, repo_dir)
    print(f"Indexing repo at: {repo_dir}")
    print(f"Writing index files to: {output_dir}")

    file_count = 0
    unit_count = 0
    import_count = 0

    with files_path.open("w", encoding="utf-8") as files_handle, units_path.open(
        "w", encoding="utf-8"
    ) as units_handle, imports_path.open("w", encoding="utf-8") as imports_handle:
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = filter_ignored_dirs(dirs, ignore_patterns)
            root_path = Path(root)
            for filename in files:
                file_path = root_path / filename
                rel_path = file_path.relative_to(repo_dir)
                if should_ignore(file_path, ignore_patterns):
                    continue
                # Read file bytes once to compute hash and decide if it's text.
                try:
                    data = file_path.read_bytes()
                except OSError:
                    logger.warning("Failed to read %s", file_path)
                    continue
                size_bytes = file_path.stat().st_size
                is_text = _is_text_file(file_path)
                text = None
                n_lines = 0
                if is_text:
                    text = data.decode("utf-8")
                    n_lines = len(text.splitlines())
                record = {
                    "path": str(rel_path),
                    "abs_path": str(file_path),
                    "size_bytes": size_bytes,
                    "sha256": _sha256_bytes(data),
                    "language": _language_for_path(file_path),
                    "is_text": is_text,
                    "n_lines": n_lines,
                }
                files_handle.write(json.dumps(record) + "\n")
                file_count += 1

                if not is_text or text is None:
                    continue

                for unit in chunk_text(rel_path, text):
                    units_handle.write(json.dumps(unit) + "\n")
                    unit_count += 1

                if file_path.suffix.lower() == ".py":
                    for imp in extract_imports(rel_path, text, repo_dir):
                        imports_handle.write(json.dumps(asdict(imp)) + "\n")
                        import_count += 1

    print(f"Indexed {file_count} files")
    print(f"Wrote {unit_count} units and {import_count} import records")
    return output_dir
