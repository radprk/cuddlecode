from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class PythonUnit:
    unit_id: str
    path: str
    start_line: int
    end_line: int
    kind: str
    symbol: str
    signature: str
    text: str


@dataclass(frozen=True)
class PythonImport:
    src_path: str
    imported_module: str
    resolved_path: Optional[str]


def _format_args(args: ast.arguments) -> str:
    try:
        return ast.unparse(args)
    except Exception:
        return "..."


def _function_signature(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = _format_args(node.args)
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({args})"
    if isinstance(node, ast.ClassDef):
        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                bases.append("...")
        bases_text = f"({', '.join(bases)})" if bases else ""
        return f"class {node.name}{bases_text}"
    return ""


def extract_units(path: Path, text: str) -> list[PythonUnit]:
    """Extract function/class units from Python source using AST line ranges."""
    tree = ast.parse(text)
    units: list[PythonUnit] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
                continue
            start_line = int(node.lineno)
            end_line = int(node.end_lineno)
            # Pull the exact source for the node for downstream LLM context.
            source = ast.get_source_segment(text, node)
            if source is None:
                lines = text.splitlines()
                source = "\n".join(lines[start_line - 1 : end_line])
            signature = _function_signature(node)
            unit_id = f"{path}:{start_line}-{end_line}:{node.name}"
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            units.append(
                PythonUnit(
                    unit_id=unit_id,
                    path=str(path),
                    start_line=start_line,
                    end_line=end_line,
                    kind=kind,
                    symbol=node.name,
                    signature=signature,
                    text=source,
                )
            )
    return sorted(units, key=lambda unit: unit.start_line)


def _resolve_module(module: str, repo_root: Path, src_path: Path, level: int) -> Optional[str]:
    """Best-effort resolver for intra-repo Python imports."""
    if level > 0:
        base_dir = src_path.parent
        for _ in range(level - 1):
            base_dir = base_dir.parent
        module_path = Path(*module.split(".")) if module else Path(".")
        candidate = (base_dir / module_path).resolve()
    else:
        candidate = (repo_root / Path(*module.split("."))).resolve()

    file_candidate = candidate.with_suffix(".py")
    if file_candidate.exists():
        return str(file_candidate)
    init_candidate = candidate / "__init__.py"
    if init_candidate.exists():
        return str(init_candidate)
    return None


def extract_imports(path: Path, text: str, repo_root: Path) -> Iterable[PythonImport]:
    """Extract import statements and resolve intra-repo module paths when possible."""
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                resolved = _resolve_module(module, repo_root, path, 0)
                yield PythonImport(
                    src_path=str(path),
                    imported_module=module,
                    resolved_path=resolved,
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported_module = "." * node.level + module
            resolved = _resolve_module(module, repo_root, path, node.level)
            yield PythonImport(
                src_path=str(path),
                imported_module=imported_module,
                resolved_path=resolved,
            )
