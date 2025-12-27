from __future__ import annotations

from pathlib import Path

from ingest.chunking import ChunkConfig, chunk_text


def _assert_line_accuracy(text: str, units: list[dict]) -> None:
    lines = text.splitlines()
    for unit in units:
        start = unit["start_line"]
        end = unit["end_line"]
        expected = "\n".join(lines[start - 1 : end])
        assert expected == unit["text"]


def test_split_large_structured_block() -> None:
    heading = "# Big Section"
    body = "\n".join(["paragraph line" for _ in range(200)])
    text = f"{heading}\n{body}\n"
    config = ChunkConfig(max_chars=200, target_chars=120, min_chars=50, overlap_lines=2, header_max_chars=50)
    units = chunk_text(Path("README.md"), text, config)

    split_units = [unit for unit in units if unit["kind"].endswith("_part")]
    assert split_units
    assert all(len(unit["text"]) <= config.max_chars for unit in units)
    _assert_line_accuracy(text, units)


def test_merge_small_blocks() -> None:
    text = "\n".join(
        [
            "# One",
            "short",
            "# Two",
            "tiny",
            "# Three",
            "small",
        ]
    )
    config = ChunkConfig(max_chars=200, target_chars=120, min_chars=80, overlap_lines=1, header_max_chars=30)
    units = chunk_text(Path("notes.md"), text, config)

    merged_units = [unit for unit in units if unit["kind"] == "merged"]
    assert merged_units
    assert all(len(unit["text"]) <= config.max_chars for unit in units)
    _assert_line_accuracy(text, units)


def test_mixed_structure_and_fallback() -> None:
    text = "\n".join(
        [
            "Intro line",
            "Another intro",
            "# Section",
            "Section line",
            "Trailing text without heading",
        ]
    )
    config = ChunkConfig(max_chars=200, target_chars=120, min_chars=20, overlap_lines=1, header_max_chars=30)
    units = chunk_text(Path("doc.md"), text, config)

    kinds = {unit["kind"] for unit in units}
    assert "file_header" in kinds
    assert "section" in kinds
    _assert_line_accuracy(text, units)


def test_unit_id_stability() -> None:
    text = "\n".join(["# Title", "line one", "line two", "line three"])
    config = ChunkConfig(max_chars=200, target_chars=120, min_chars=20, overlap_lines=1, header_max_chars=30)
    units_a = chunk_text(Path("doc.md"), text, config)
    units_b = chunk_text(Path("doc.md"), text, config)
    assert [unit["unit_id"] for unit in units_a] == [unit["unit_id"] for unit in units_b]
