from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

DEFAULT_IGNORES = (
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    "coverage",
    ".pytest_cache",
    "*.lock",
    "*.min.*",
    "*.png",
    "*.jpg",
    "*.pdf",
    "*.zip",
    "*.bin",
)


@dataclass(frozen=True)
class IgnoreSpec:
    patterns: tuple[str, ...] = field(default_factory=lambda: DEFAULT_IGNORES)

    def is_ignored(self, path: Path) -> bool:
        name = path.name
        for pattern in self.patterns:
            if fnmatch(name, pattern):
                return True
        return False

    def should_skip(self, rel_path: Path) -> bool:
        for part in rel_path.parts:
            if self.is_ignored(Path(part)):
                return True
        return self.is_ignored(rel_path)

    @classmethod
    def from_iterable(cls, items: Iterable[str] | None) -> "IgnoreSpec":
        if not items:
            return cls()
        return cls(patterns=tuple(items))
