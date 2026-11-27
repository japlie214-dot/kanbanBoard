"""kb_repo_id.py – Git-Root Repo Identity Resolver (v4 Auto-Doc & Zero-Duplicate Board Foundation).

Maps any messy local directory to its canonical Kanban project using:
  1. Immutable git root commit SHA (`git rev-list --max-parents=0 HEAD`) — survives folder renames & remote changes.
  2. Git remote URL (`git remote get-url origin`).
  3. Git top-level directory (`git rev-parse --show-toplevel`).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import kb_crud


def _git(cmd: list[str], cwd: Path) -> str:
    try:
        proc = subprocess.run(["git", *cmd], cwd=str(cwd), capture_output=True, text=True, timeout=5)
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except Exception:
        return ""


def resolve_repo_identity(cwd: str | Path) -> dict[str, str]:
    p = Path(cwd).resolve()
    toplevel = _git(["rev-parse", "--show-toplevel"], p)
    root_commits = _git(["rev-list", "--max-parents=0", "HEAD"], p).splitlines()
    remote = _git(["remote", "get-url", "origin"], p)
    head = _git(["rev-parse", "--short", "HEAD"], p)
    return {
        "toplevel": toplevel.replace("\\", "/"),
        "root_commit": root_commits[0].strip() if root_commits else "",
        "remote": remote,
        "head": head,
    }


def match_project_by_repo(cwd: str | Path, board: Path) -> str | None:
    """Match cwd's git identity against `project.md` frontmatter (`repo_root_commit`, `repo_remote`, `repo_paths`)."""
    ident = resolve_repo_identity(cwd)
    if not board.exists():
        return None
    norm_top = ident["toplevel"].rstrip("/").lower()
    for proj_md in sorted(board.glob("*/project.md")):
        try:
            meta, _ = kb_crud.split_frontmatter(proj_md.read_text(encoding="utf-8"))
        except Exception:
            continue
        slug = proj_md.parent.name
        if ident["root_commit"] and str(meta.get("repo_root_commit") or "").strip() == ident["root_commit"]:
            return slug
        if ident["remote"] and str(meta.get("repo_remote") or "").strip().lower() == ident["remote"].lower():
            return slug
        paths = meta.get("repo_paths") or []
        if isinstance(paths, str):
            paths = [paths]
        for rp in paths:
            if norm_top and str(rp).replace("\\", "/").rstrip("/").lower() == norm_top:
                return slug
    return None
