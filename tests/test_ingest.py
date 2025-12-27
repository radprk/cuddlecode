from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest.indexer import index_repo_dir


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def create_repo(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "repos" / "toy" / "deadbeef"
    repo_dir.mkdir(parents=True)
    (repo_dir / "node_modules").mkdir()
    (repo_dir / "node_modules" / "ignored.txt").write_text("ignore me")
    (repo_dir / "helpers.py").write_text(
        "def helper():\n"
        "    return 1\n"
    )
    (repo_dir / "sample.py").write_text(
        "import os\n"
        "import helpers\n\n"
        "def first():\n"
        "    \"\"\"docstring\"\"\"\n"
        "    return 1\n\n"
        "def second():\n"
        "    return 2\n\n"
        "class Greeter:\n"
        "    \"\"\"class doc\"\"\"\n"
        "    def greet(self):\n"
        "        return 'hi'\n"
    )
    (repo_dir / "notes.txt").write_text("line1\nline2\n")
    (repo_dir / "image.bin").write_bytes(b"\x00\x01\x02")
    return repo_dir


def test_indexing_outputs_and_ignores(tmp_path: Path) -> None:
    repo_dir = create_repo(tmp_path)
    output_root = tmp_path / "indexes"

    result = index_repo_dir(str(repo_dir), output_root=str(output_root))

    manifest = read_jsonl(result.manifest_path)
    paths = {record["path"] for record in manifest}

    assert "node_modules/ignored.txt" not in paths
    assert "sample.py" in paths

    units = read_jsonl(result.units_path)
    unit_paths = {record["path"] for record in units}
    assert "image.bin" not in unit_paths
    assert "notes.txt" in unit_paths


def test_python_chunking_and_imports(tmp_path: Path) -> None:
    repo_dir = create_repo(tmp_path)
    output_root = tmp_path / "indexes"

    result = index_repo_dir(str(repo_dir), output_root=str(output_root))

    units = read_jsonl(result.units_path)
    py_units = [u for u in units if u["path"] == "sample.py"]

    symbols = {u["symbol"] for u in py_units}
    assert {"first", "second", "Greeter"}.issubset(symbols)

    for unit in py_units:
        assert unit["start_line"] <= unit["end_line"]

    imports = read_jsonl(result.imports_path)
    imported = {record["imported_module"] for record in imports}
    assert "os" in imported
    assert "helpers" in imported

    helpers_records = [r for r in imports if r["imported_module"] == "helpers"]
    assert helpers_records
    assert helpers_records[0]["resolved_path"] == "helpers.py"
