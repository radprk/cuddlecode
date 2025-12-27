from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterable


def should_ignore(path: Path, patterns: Iterable[str]) -> bool:
    name = path.name
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def filter_ignored_dirs(dirs: list[str], patterns: Iterable[str]) -> list[str]:
    kept = []
    for dirname in dirs:
        if not should_ignore(Path(dirname), patterns):
            kept.append(dirname)
    return kept
