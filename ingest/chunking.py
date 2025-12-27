from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from ingest.constants import (
    DEFAULT_HEADER_MAX_CHARS,
    DEFAULT_MAX_CHARS,
    DEFAULT_MIN_CHARS,
    DEFAULT_OVERLAP_LINES,
    DEFAULT_TARGET_CHARS,
)
from ingest.python_ast import extract_top_level_units


@dataclass(frozen=True)
class ChunkConfig:
    max_chars: int = DEFAULT_MAX_CHARS
    target_chars: int = DEFAULT_TARGET_CHARS
    min_chars: int = DEFAULT_MIN_CHARS
    overlap_lines: int = DEFAULT_OVERLAP_LINES
    header_max_chars: int = DEFAULT_HEADER_MAX_CHARS


HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(?P<title>.+?)\s*$")
KEY_RE = re.compile(r"^(?P<key>[A-Za-z0-9_.-]+)\s*:")
PY_DEF_RE = re.compile(r"^\s*(def|class)\s+\w+")


def _slice_lines(lines: list[str], start_line: int, end_line: int) -> str:
    return "\n".join(lines[start_line - 1 : end_line])


def _line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + 1


def _unit_id(path: Path, start_line: int, end_line: int, kind_or_symbol: str) -> str:
    return f"{path}:{start_line}-{end_line}:{kind_or_symbol}"


def _find_header_end(lines: list[str], config: ChunkConfig, boundary_line: Optional[int]) -> int:
    if not lines:
        return 0
    limit = min(config.header_max_chars, config.max_chars)
    end_line = 0
    chars = 0
    max_line = boundary_line - 1 if boundary_line else len(lines)
    for idx in range(1, max_line + 1):
        line = lines[idx - 1]
        chars += len(line) + 1
        if chars > limit:
            break
        end_line = idx
    return max(end_line, 1)


def _detect_boundary(lines: list[str]) -> Optional[int]:
    for idx, line in enumerate(lines, start=1):
        if HEADING_RE.match(line):
            return idx
        if PY_DEF_RE.match(line):
            return idx
        if KEY_RE.match(line) and not line.startswith(" "):
            return idx
    return None


def _structural_blocks_from_headings(lines: list[str], start_line: int) -> list[dict]:
    headings = []
    for idx in range(start_line, len(lines) + 1):
        match = HEADING_RE.match(lines[idx - 1])
        if match:
            headings.append((idx, match.group("title").strip()))
    blocks = []
    for index, (line_no, title) in enumerate(headings):
        end_line = headings[index + 1][0] - 1 if index + 1 < len(headings) else len(lines)
        blocks.append(
            {
                "start_line": line_no,
                "end_line": end_line,
                "kind": "section",
                "symbol": title,
                "signature": None,
            }
        )
    return blocks


def _structural_blocks_from_keys(lines: list[str], start_line: int) -> list[dict]:
    keys = []
    for idx in range(start_line, len(lines) + 1):
        line = lines[idx - 1]
        if line.startswith(" "):
            continue
        match = KEY_RE.match(line)
        if match:
            keys.append((idx, match.group("key")))
    blocks = []
    for index, (line_no, key) in enumerate(keys):
        end_line = keys[index + 1][0] - 1 if index + 1 < len(keys) else len(lines)
        blocks.append(
            {
                "start_line": line_no,
                "end_line": end_line,
                "kind": "block",
                "symbol": key,
                "signature": None,
            }
        )
    return blocks


def _structural_blocks(path: Path, lines: list[str], start_line: int) -> list[dict]:
    if path.suffix.lower() == ".py":
        try:
            units = extract_top_level_units(path, "\n".join(lines))
        except SyntaxError:
            units = []
        blocks = [
            {
                "start_line": unit.start_line,
                "end_line": unit.end_line,
                "kind": unit.kind,
                "symbol": unit.symbol,
                "signature": unit.signature,
            }
            for unit in units
            if unit.start_line >= start_line
        ]
        if blocks:
            return blocks

    heading_blocks = _structural_blocks_from_headings(lines, start_line)
    if heading_blocks:
        return heading_blocks

    return _structural_blocks_from_keys(lines, start_line)


def _fill_gaps(blocks: list[dict], start_line: int, end_line: int) -> list[dict]:
    if start_line > end_line:
        return []
    if not blocks:
        return [
            {
                "start_line": start_line,
                "end_line": end_line,
                "kind": "chunk",
                "symbol": None,
                "signature": None,
            }
        ]
    blocks = sorted(blocks, key=lambda block: block["start_line"])
    filled: list[dict] = []
    cursor = start_line
    for block in blocks:
        if block["start_line"] > cursor:
            filled.append(
                {
                    "start_line": cursor,
                    "end_line": block["start_line"] - 1,
                    "kind": "chunk",
                    "symbol": None,
                    "signature": None,
                }
            )
        filled.append(block)
        cursor = max(cursor, block["end_line"] + 1)
    if cursor <= end_line:
        filled.append(
            {
                "start_line": cursor,
                "end_line": end_line,
                "kind": "chunk",
                "symbol": None,
                "signature": None,
            }
        )
    return filled


def _split_large_unit(
    path: Path,
    lines: list[str],
    unit: dict,
    config: ChunkConfig,
) -> list[dict]:
    text = _slice_lines(lines, unit["start_line"], unit["end_line"])
    if len(text) <= config.max_chars:
        return [
            {
                **unit,
                "unit_id": _unit_id(path, unit["start_line"], unit["end_line"], unit["symbol"] or unit["kind"]),
                "text": text,
            }
        ]

    parts: list[dict] = []
    start = unit["start_line"]
    end = unit["end_line"]
    part_index = 1
    while start <= end:
        chars = 0
        last_boundary: Optional[int] = None
        split_end = end
        for line_no in range(start, end + 1):
            line = lines[line_no - 1]
            line_len = len(line) + 1
            if chars + line_len > config.max_chars:
                if last_boundary and last_boundary >= start:
                    split_end = last_boundary
                else:
                    split_end = max(line_no - 1, start)
                break
            chars += line_len
            if not line.strip() or HEADING_RE.match(line) or KEY_RE.match(line):
                last_boundary = line_no
        part_text = _slice_lines(lines, start, split_end)
        part_unit = {
            **unit,
            "start_line": start,
            "end_line": split_end,
            "kind": f"{unit['kind']}_part",
            "unit_id": _unit_id(
                path,
                start,
                split_end,
                f"{unit['symbol'] or unit['kind']}#part{part_index}",
            ),
            "text": part_text,
        }
        parts.append(part_unit)
        if split_end >= end:
            break
        start = max(split_end - config.overlap_lines + 1, start + 1)
        part_index += 1
    return parts


def _merge_small_units(
    path: Path,
    lines: list[str],
    units: list[dict],
    config: ChunkConfig,
) -> list[dict]:
    merged: list[dict] = []
    idx = 0
    while idx < len(units):
        unit = units[idx]
        if unit["kind"] == "file_header":
            merged.append(unit)
            idx += 1
            continue
        current_start = unit["start_line"]
        current_end = unit["end_line"]
        symbols = [unit["symbol"]] if unit["symbol"] else []
        text = _slice_lines(lines, current_start, current_end)
        if len(text) >= config.min_chars:
            merged.append(unit)
            idx += 1
            continue

        if merged and merged[-1]["kind"] != "file_header":
            prev = merged[-1]
            merged_start = prev["start_line"]
            merged_end = current_end
            merged_text = _slice_lines(lines, merged_start, merged_end)
            if len(merged_text) <= config.max_chars:
                prev_symbols = [prev["symbol"]] if prev["symbol"] else []
                combined_symbols = [symbol for symbol in prev_symbols + symbols if symbol]
                merged[-1] = {
                    "unit_id": _unit_id(path, merged_start, merged_end, "merged"),
                    "path": str(path),
                    "start_line": merged_start,
                    "end_line": merged_end,
                    "kind": "merged",
                    "symbol": "+".join(combined_symbols) if combined_symbols else None,
                    "signature": None,
                    "text": merged_text,
                }
                idx += 1
                continue

        total_chars = len(text)
        next_idx = idx + 1
        while next_idx < len(units) and total_chars < config.target_chars:
            next_unit = units[next_idx]
            if next_unit["kind"] == "file_header":
                break
            next_text = _slice_lines(lines, current_start, next_unit["end_line"])
            if len(next_text) > config.max_chars:
                break
            total_chars = len(next_text)
            current_end = next_unit["end_line"]
            if next_unit["symbol"]:
                symbols.append(next_unit["symbol"])
            next_idx += 1
        merged_text = _slice_lines(lines, current_start, current_end)
        merged.append(
            {
                "unit_id": _unit_id(path, current_start, current_end, "merged"),
                "path": str(path),
                "start_line": current_start,
                "end_line": current_end,
                "kind": "merged",
                "symbol": "+".join(symbols) if symbols else None,
                "signature": None,
                "text": merged_text,
            }
        )
        idx = next_idx
    return merged


def chunk_text(path: Path, text: str, config: Optional[ChunkConfig] = None) -> list[dict]:
    """Chunk a text file into structure-aware, size-normalized units."""
    if config is None:
        config = ChunkConfig()
    lines = text.splitlines()
    if not lines:
        return []

    boundary = _detect_boundary(lines)
    header_end = _find_header_end(lines, config, boundary)
    header_text = _slice_lines(lines, 1, header_end)
    header_unit = {
        "unit_id": _unit_id(path, 1, header_end, "file_header"),
        "path": str(path),
        "start_line": 1,
        "end_line": header_end,
        "kind": "file_header",
        "symbol": None,
        "signature": None,
        "text": header_text,
    }

    blocks = _structural_blocks(path, lines, header_end + 1)
    blocks = _fill_gaps(blocks, header_end + 1, len(lines))

    candidates: list[dict] = [header_unit]
    for block in blocks:
        candidates.append(
            {
                "unit_id": _unit_id(path, block["start_line"], block["end_line"], block["symbol"] or block["kind"]),
                "path": str(path),
                "start_line": block["start_line"],
                "end_line": block["end_line"],
                "kind": block["kind"],
                "symbol": block["symbol"],
                "signature": block["signature"],
                "text": _slice_lines(lines, block["start_line"], block["end_line"]),
            }
        )

    normalized: list[dict] = []
    for unit in candidates:
        normalized.extend(_split_large_unit(path, lines, unit, config))

    merged = _merge_small_units(path, lines, normalized, config)
    return [unit for unit in merged if unit["text"]]
