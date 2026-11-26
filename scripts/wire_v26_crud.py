#!/usr/bin/env python3
"""scripts/wire_v26_crud.py – Wires kb_crud.py (retire/restore/rehome/purge + LLM pagination) into mcp_server.py.

Usage:
  python scripts/wire_v26_crud.py --dry-run   # Print exact unified diff without modifying files
  python scripts/wire_v26_crud.py --apply     # Apply verified edits to mcp_server.py
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch_mcp_server(src: str) -> str:
    out = src
    if "import kb_crud" not in out and "import kb\n" in out:
        out = out.replace("import kb\n", "import kb\nimport kb_crud\n", 1)

    # 1. Expand kanban_ticket action enum to full CRUD (no scaffold!)
    out = out.replace(
        '["show", "create", "edit"]',
        '["show", "create", "edit", "retire", "restore", "rehome"]',
    )
    out = out.replace(
        "['show', 'create', 'edit']",
        "['show', 'create', 'edit', 'retire', 'restore', 'rehome']",
    )

    # 2. Inject retire / restore / rehome dispatch right inside kanban_ticket handler if not already wired
    if 'action == "retire"' not in out:
        anchor = 'if action == "show":'
        injection = (
            'if action == "retire":\n'
            '        res = kb_crud.api_retire(ref, str(args.get("reason") or args.get("note") or ""), board, int(args.get("purge_after_days") or 120))\n'
            '        return json.dumps(res, indent=2)\n'
            '    if action == "restore":\n'
            '        res = kb_crud.api_restore(ref, board, str(args.get("note") or "Restored to active backlog"))\n'
            '        return json.dumps(res, indent=2)\n'
            '    if action == "rehome":\n'
            '        res = kb_crud.api_rehome(ref, str(args.get("new_epic") or ""), board, args.get("new_project"))\n'
            '        return json.dumps(res, indent=2)\n'
            '    if action == "show":'
        )
        if anchor in out:
            out = out.replace(anchor, injection, 1)

    # 3. Add pagination + include_retired schema properties to kanban_board if absent
    if '"page_size"' not in out:
        board_anchor = '"status": {"type": "string"'
        if board_anchor in out:
            out = out.replace(
                board_anchor,
                '"page": {"type": "integer", "description": "1-based page number (default 1)"},\n'
                '                    "page_size": {"type": "integer", "description": "Items per page (default 25, max 100)"},\n'
                '                    "q": {"type": "string", "description": "Optional search query across ref, title, owner"},\n'
                '                    "include_retired": {"type": "boolean", "description": "Include retired backlog tickets (default false)"},\n'
                '                    "status": {"type": "string"',
                1,
            )

    return out


def show_diff(path: Path, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Wire v2.6 CRUD + pagination into mcp_server.py")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    target = ROOT / "mcp_server.py"
    if not target.is_file():
        print(f"[SKIP] {target} not found", file=sys.stderr)
        return 1

    old = target.read_text(encoding="utf-8")
    new = patch_mcp_server(old)
    if old == new:
        print("[OK] mcp_server.py already wired for v2.6 CRUD & pagination.")
        return 0

    print(show_diff(target, old, new))
    if args.apply:
        target.write_text(new, encoding="utf-8", newline="\n")
        print("[APPLIED] mcp_server.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
