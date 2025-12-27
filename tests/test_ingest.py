from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ingest.constants import DEFAULT_IGNORE_PATTERNS
from ingest.indexer import index_repo
from ingest.ignore import should_ignore


@pytest.fixture()
def toy_repo(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "toy"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True)
    (repo_dir / "module.py").write_text(
        """
import os
from . import helper

def first():
    \"\"\"First function.\"\"\"
    return 1


def second():
    return 2


class Example:
    def method(self):
        return 3
""".lstrip(),
        encoding="utf-8",
    )
    (repo_dir / "helper.py").write_text("value = 1\n", encoding="utf-8")
    (repo_dir / "binary.bin").write_bytes(b"\x00\x01\x02")
    (repo_dir / "node_modules").mkdir()
    (repo_dir / "node_modules" / "ignored.js").write_text("console.log('x')", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True)
    return repo_dir


def test_ignore_rules() -> None:
    assert should_ignore(Path("node_modules"), DEFAULT_IGNORE_PATTERNS)
    assert should_ignore(Path("file.lock"), DEFAULT_IGNORE_PATTERNS)
    assert not should_ignore(Path("src"), DEFAULT_IGNORE_PATTERNS)


def test_manifest_and_units(toy_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = index_repo(toy_repo)
    files = list((output_dir / "files.jsonl").read_text(encoding="utf-8").splitlines())
    units = list((output_dir / "units.jsonl").read_text(encoding="utf-8").splitlines())
    assert files
    assert units
    unit_records = [json.loads(line) for line in units]
    assert all("binary.bin" not in unit["path"] for unit in unit_records)


def test_python_units_and_imports(toy_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = index_repo(toy_repo)
    units = [json.loads(line) for line in (output_dir / "units.jsonl").read_text(encoding="utf-8").splitlines()]
    names = {unit["symbol"] for unit in units if unit["path"] == "module.py"}
    assert {"first", "second", "Example"}.issubset(names)
    module_units = [unit for unit in units if unit["path"] == "module.py"]
    assert len(module_units) >= 3
    for unit in module_units:
        assert unit["start_line"] < unit["end_line"]

    imports = [
        json.loads(line)
        for line in (output_dir / "imports.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    imported = {imp["imported_module"] for imp in imports if imp["src_path"] == "module.py"}
    assert "os" in imported
    assert ".helper" in imported or "." in imported
