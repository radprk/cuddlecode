from __future__ import annotations

import ast
from pathlib import Path

from .models import ImportRecord


def build_imports(text: str, path: str, repo_root: Path) -> list[ImportRecord]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    src_path = path
    src_dir = Path(path).parent
    records: list[ImportRecord] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                resolved = resolve_module(
                    repo_root=repo_root,
                    src_dir=src_dir,
                    module=module_name,
                    level=0,
                    name_for_from=None,
                )
                records.append(
                    ImportRecord(
                        src_path=src_path,
                        imported_module=module_name,
                        resolved_path=resolved,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level = node.level or 0
            for alias in node.names:
                if module:
                    imported = f"{module}.{alias.name}"
                else:
                    imported = alias.name
                prefix = "." * level
                imported_module = f"{prefix}{imported}" if prefix else imported
                resolved = resolve_module(
                    repo_root=repo_root,
                    src_dir=src_dir,
                    module=module,
                    level=level,
                    name_for_from=alias.name,
                )
                records.append(
                    ImportRecord(
                        src_path=src_path,
                        imported_module=imported_module,
                        resolved_path=resolved,
                    )
                )

    return records


def resolve_module(
    repo_root: Path,
    src_dir: Path,
    module: str,
    level: int,
    name_for_from: str | None,
) -> str | None:
    base_dir = src_dir
    if level > 1:
        for _ in range(level - 1):
            base_dir = base_dir.parent
    elif level == 0:
        base_dir = repo_root

    candidates = []
    if module:
        if name_for_from:
            candidates.append(f"{module}.{name_for_from}")
        candidates.append(module)
    elif name_for_from:
        candidates.append(name_for_from)

    for module_name in candidates:
        rel_path = Path(*module_name.split("."))
        for suffix in (".py", ""):
            candidate = base_dir / f"{rel_path}{suffix}"
            if suffix == "":
                candidate = base_dir / rel_path / "__init__.py"
            if candidate.exists():
                try:
                    return candidate.relative_to(repo_root).as_posix()
                except ValueError:
                    return candidate.as_posix()

    return None
