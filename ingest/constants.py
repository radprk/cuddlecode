DEFAULT_IGNORE_PATTERNS = [
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
]

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".md": "markdown",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
}

DEFAULT_MAX_CHARS = 8000
DEFAULT_TARGET_CHARS = 4000
DEFAULT_MIN_CHARS = 500
DEFAULT_OVERLAP_LINES = 8
DEFAULT_HEADER_MAX_CHARS = 1200
