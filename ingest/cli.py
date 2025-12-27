from __future__ import annotations

import argparse
import logging
from pathlib import Path

from ingest.clone import clone_repo
from ingest.indexer import index_repo


def _configure_logging() -> None:
    """Enable INFO logging for CLI runs."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _parse_args() -> argparse.Namespace:
    """Parse CLI args for clone/index/all commands."""
    parser = argparse.ArgumentParser(prog="python -m ingest", description="Repo ingestion CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Clone: repo URL can be positional or flagged, plus optional branch/commit.
    clone_parser = subparsers.add_parser("clone", help="Clone a repository")
    clone_parser.add_argument("repo", nargs="?", help="Repository URL")
    clone_parser.add_argument("--repo", dest="repo_flag", help="Repository URL (flag)")
    clone_parser.add_argument("--branch", help="Branch name")
    clone_parser.add_argument("--commit", help="Commit SHA")

    # Index: operate on an existing repo directory.
    index_parser = subparsers.add_parser("index", help="Index a local repository")
    index_parser.add_argument("--repo_dir", required=True, help="Path to repo")

    # All: clone then index in a single command.
    all_parser = subparsers.add_parser("all", help="Clone and index")
    all_parser.add_argument("repo", nargs="?", help="Repository URL")
    all_parser.add_argument("--repo", dest="repo_flag", help="Repository URL (flag)")
    all_parser.add_argument("--branch", help="Branch name")
    all_parser.add_argument("--commit", help="Commit SHA")

    return parser.parse_args()


def _prompt_repo_url() -> str:
    """Ask the user for a repo URL when not provided on the CLI."""
    return input("Enter the GitHub repo URL (https or ssh): ").strip()


def main() -> None:
    """Dispatch CLI commands for cloning and indexing."""
    _configure_logging()
    args = _parse_args()
    if args.command == "clone":
        repo = args.repo or args.repo_flag or _prompt_repo_url()
        print(f"Cloning repo: {repo}")
        clone_repo(repo, branch=args.branch, commit_sha=args.commit)
        return
    if args.command == "index":
        print(f"Indexing local repo: {args.repo_dir}")
        index_repo(Path(args.repo_dir))
        return
    if args.command == "all":
        repo = args.repo or args.repo_flag or _prompt_repo_url()
        print(f"Cloning and indexing repo: {repo}")
        repo_dir = clone_repo(repo, branch=args.branch, commit_sha=args.commit)
        index_repo(repo_dir)
        return


if __name__ == "__main__":
    main()
