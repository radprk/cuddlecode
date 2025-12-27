from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileRecord:
    path: str
    abs_path: str
    size_bytes: int
    sha256: str
    language: str | None
    is_text: bool
    n_lines: int | None


@dataclass(frozen=True)
class UnitRecord:
    unit_id: str
    path: str
    start_line: int
    end_line: int
    kind: str
    symbol: str | None
    signature: str | None
    text: str


@dataclass(frozen=True)
class ImportRecord:
    src_path: str
    imported_module: str
    resolved_path: str | None


@dataclass(frozen=True)
class IndexResult:
    repo_name: str
    commit_sha: str
    manifest_path: Path
    units_path: Path
    imports_path: Path
