from __future__ import annotations

import ast
from dataclasses import dataclass

from .models import UnitRecord

DEFAULT_MAX_LINES = 200
DEFAULT_OVERLAP = 20


@dataclass(frozen=True)
class LineRange:
    start: int
    end: int


def chunk_text_file(
    text: str,
    path: str,
    max_lines: int = DEFAULT_MAX_LINES,
    overlap: int = DEFAULT_OVERLAP,
) -> list[UnitRecord]:
    lines = text.splitlines()
    if not lines:
        return []
    units: list[UnitRecord] = []
    step = max_lines - overlap
    start = 0
    unit_index = 0
    while start < len(lines):
        end = min(start + max_lines, len(lines))
        chunk_lines = lines[start:end]
        start_line = start + 1
        end_line = end
        unit_id = f"{path}:{start_line}-{end_line}:{unit_index}"
        units.append(
            UnitRecord(
                unit_id=unit_id,
                path=path,
                start_line=start_line,
                end_line=end_line,
                kind="chunk",
                symbol=None,
                signature=None,
                text="\n".join(chunk_lines),
            )
        )
        unit_index += 1
        if end == len(lines):
            break
        start += step
    return units


def chunk_python_file(text: str, path: str) -> list[UnitRecord]:
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return chunk_text_file(text, path)

    units: list[UnitRecord] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            units.append(_unit_from_node(node, lines, path, kind="function"))
        elif isinstance(node, ast.ClassDef):
            units.append(_unit_from_node(node, lines, path, kind="class"))

    return units


def _unit_from_node(
    node: ast.AST,
    lines: list[str],
    path: str,
    kind: str,
) -> UnitRecord:
    start_line = getattr(node, "lineno", 1)
    end_line = getattr(node, "end_lineno", start_line)
    segment = lines[start_line - 1 : end_line]
    signature_line = lines[start_line - 1].strip() if lines else ""
    symbol = getattr(node, "name", None)
    unit_id = f"{path}:{start_line}-{end_line}:{symbol or kind}"
    return UnitRecord(
        unit_id=unit_id,
        path=path,
        start_line=start_line,
        end_line=end_line,
        kind=kind,
        symbol=symbol,
        signature=signature_line,
        text="\n".join(segment),
    )
