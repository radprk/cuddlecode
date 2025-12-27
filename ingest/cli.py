from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from .git_ops import clone_repo
from .indexer import index_repo_dir

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest Git repositories for indexing.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    clone_parser = subparsers.add_parser("clone", help="Clone a repository.")
    clone_parser.add_argument("--repo", required=True, help="Git repo URL")
    clone_parser.add_argument("--branch", help="Branch name")
    clone_parser.add_argument("--commit", help="Commit SHA")

    index_parser = subparsers.add_parser("index", help="Index a repository directory.")
    index_parser.add_argument("--repo_dir", required=True, help="Path to repo dir")

    all_parser = subparsers.add_parser("all", help="Clone then index a repository.")
    all_parser.add_argument("--repo", required=True, help="Git repo URL")
    all_parser.add_argument("--branch", help="Branch name")
    all_parser.add_argument("--commit", help="Commit SHA")

    return parser


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(argv: Sequence[str] | None = None) -> None:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "clone":
        result = clone_repo(args.repo, branch=args.branch, commit_sha=args.commit)
        LOGGER.info("Cloned %s at %s", result.repo_name, result.repo_dir)
        return

    if args.command == "index":
        result = index_repo_dir(args.repo_dir)
        LOGGER.info("Indexed %s at %s", result.repo_name, result.manifest_path.parent)
        return

    if args.command == "all":
        clone_result = clone_repo(args.repo, branch=args.branch, commit_sha=args.commit)
        index_result = index_repo_dir(str(clone_result.repo_dir))
        LOGGER.info("Indexed %s at %s", index_result.repo_name, index_result.manifest_path.parent)
        return

    raise ValueError(f"Unknown command {args.command}")
