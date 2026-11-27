#!/usr/bin/env python3
"""scripts/migrate_in_progress_to_build.py – Safely migrate active `status: in-progress` tickets to `status: build`.

Leaves `done` tickets completely untouched so HMAC signatures remain valid.

Usage:
  python scripts/migrate_in_progress_to_build.py --dry-run
  python scripts/migrate_in_progress_to_build.py --apply
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def migrate_board(board: Path, apply: bool = False) -> list[str]:
    changed: list[str] = []
    if not board.exists():
        return changed
    pat = re.compile(r"^(status:\s*)in-progress\s*$", re.M)
    for md in sorted(board.glob("*/*/*.md")):
        if md.name.lower() in {"project.md", "epic.md", "readme.md"}:
            continue
        text = md.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        fm, body = parts[1], parts[2]
        if not pat.search(fm):
            continue
        new_fm = pat.sub(r"\g<1>build", fm, count=1)
        rel = str(md.relative_to(board)).replace("\\", "/")
        changed.append(rel)
        if apply:
            md.write_text(f"---{new_fm}---{body}", encoding="utf-8", newline="\n")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate active in-progress tickets to build")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--board-root", default=None)
    args = parser.parse_args()

    board = Path(args.board_root).resolve() if args.board_root else (ROOT / "board")
    changed = migrate_board(board, apply=args.apply)
    tag = "MIGRATED" if args.apply else "WOULD MIGRATE"
    for item in changed:
        print(f"[{tag}] {item}: in-progress -> build")
    print(f"Total: {len(changed)} ticket(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
