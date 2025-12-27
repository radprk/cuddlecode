from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from .chunking import chunk_python_file, chunk_text_file
from .ignore import IgnoreSpec
from .imports import build_imports
from .models import FileRecord, ImportRecord, IndexResult, UnitRecord
from .utils import sha256_file

LOGGER = logging.getLogger(__name__)

LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript",
    ".tsx": "TypeScript",
    ".md": "Markdown",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
}


def detect_language(path: Path) -> str | None:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower())


def is_text_file(path: Path) -> bool:
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


def iter_repo_files(repo_root: Path, ignore: IgnoreSpec) -> Iterator[Path]:
    for path in repo_root.rglob("*"):
        rel_path = path.relative_to(repo_root)
        if ignore.should_skip(rel_path):
            if path.is_dir():
                LOGGER.debug("Skipping directory %s", rel_path)
            continue
        if path.is_file():
            yield path


def create_manifest_record(path: Path, repo_root: Path) -> FileRecord:
    rel_path = path.relative_to(repo_root)
    is_text = is_text_file(path)
    n_lines: int | None
    if is_text:
        try:
            n_lines = len(path.read_text(encoding="utf-8").splitlines())
        except OSError:
            n_lines = None
    else:
        n_lines = None
    record = FileRecord(
        path=rel_path.as_posix(),
        abs_path=str(path.resolve()),
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
        language=detect_language(path),
        is_text=is_text,
        n_lines=n_lines,
    )
    return record


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def index_repo(
    repo_root: Path,
    output_root: Path,
    ignore: IgnoreSpec | None = None,
) -> IndexResult:
    ignore_spec = ignore or IgnoreSpec()
    repo_root = repo_root.resolve()
    repo_name = repo_root.parent.name
    commit_sha = repo_root.name
    output_dir = output_root / repo_name / commit_sha
    manifest_path = output_dir / "files.jsonl"
    units_path = output_dir / "units.jsonl"
    imports_path = output_dir / "imports.jsonl"

    LOGGER.info("Indexing repo %s at %s", repo_name, repo_root)

    file_records: list[FileRecord] = []
    units: list[UnitRecord] = []
    imports: list[ImportRecord] = []

    for file_path in iter_repo_files(repo_root, ignore_spec):
        record = create_manifest_record(file_path, repo_root)
        file_records.append(record)
        if record.is_text:
            language = record.language
            text = file_path.read_text(encoding="utf-8")
            if language == "Python":
                units.extend(
                    chunk_python_file(
                        text=text,
                        path=record.path,
                    )
                )
                imports.extend(
                    build_imports(
                        text=text,
                        path=record.path,
                        repo_root=repo_root,
                    )
                )
            else:
                units.extend(
                    chunk_text_file(
                        text=text,
                        path=record.path,
                    )
                )

    write_jsonl(manifest_path, [record.__dict__ for record in file_records])
    write_jsonl(units_path, [record.__dict__ for record in units])
    write_jsonl(imports_path, [record.__dict__ for record in imports])

    return IndexResult(
        repo_name=repo_name,
        commit_sha=commit_sha,
        manifest_path=manifest_path,
        units_path=units_path,
        imports_path=imports_path,
    )


def index_repo_dir(
    repo_dir: str,
    output_root: str = "./indexes",
    ignore: Sequence[str] | None = None,
) -> IndexResult:
    ignore_spec = IgnoreSpec.from_iterable(ignore)
    return index_repo(Path(repo_dir), Path(output_root), ignore_spec)
