#!/usr/bin/env python3
"""scripts/wire_v3.py – Wires v3.0 upgrades into kb.py, mcp_server.py, install_qa_lock.py, viewer.py, and board UI.

Changes applied:
  1. Renames `in-progress` -> `build` (keeping `"in-progress"` as a transparent input alias).
  2. Updates `api_qa_reject` in `kb.py` to auto-uncheck `[ACCEPTANCE:MANDATORY]` leaves on reject.
  3. Wires `kanban_case` MCP tool (`create`, `reply`, `show`, `list`, `archive`) + `kb_history` in `mcp_server.py`.
  4. Grants Antigravity `kb-qa.md` explicit CLI registry `tools: [read_file, write_file, edit_file, run_command]`
     (omitting `call_mcp_tool`, which is not a static registry component) in `scripts/install_qa_lock.py`.
  5. Adds `/api/cases`, `/api/case?id=`, `/api/history?ref=` and throttled `archive_stale_cases` to `viewer.py`.
  6. Removes duplicate `skills/kanban-qa/SKILL.md` on `--apply` (`agents/kb-qa.md` is the single source of truth).
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch_kb_py(src: str) -> str:
    out = src
    if "import kb_history" not in out and "import hmac\n" in out:
        out = out.replace("import hmac\n", "import hmac\nimport kb_history\n", 1)

    # 1. Rename in-progress -> build in status sets & transitions while keeping alias normalization
    out = out.replace('"in-progress"', '"build"')
    out = out.replace("'in-progress'", "'build'")

    # Add input alias helper if not present
    if "def normalize_status(" not in out and "VALID_STATUSES =" in out:
        out = out.replace(
            "VALID_STATUSES =",
            'def normalize_status(s: str) -> str:\n    v = (s or "").strip().lower()\n    return "build" if v == "in-progress" else v\n\n\nVALID_STATUSES =',
            1,
        )

    # 2. Auto-uncheck [ACCEPTANCE:MANDATORY] leaves inside api_qa_reject before moving to build
    if "_uncheck_mandatory_acceptance" not in out and "def api_qa_reject(" in out:
        helper = (
            "def _uncheck_mandatory_acceptance(path: Path) -> int:\n"
            '    text = path.read_text(encoding="utf-8")\n'
            '    pat = re.compile(r"^(\\s*-\\s*\\[)[xX](\\]\\s*[^\\n]*\\[ACCEPTANCE:MANDATORY\\])", re.M)\n'
            '    new_text, count = pat.subn(r"\\g<1> \\g<2>", text)\n'
            "    if count:\n"
            '        path.write_text(new_text, encoding="utf-8", newline="\\n")\n'
            "    return count\n\n\n"
            "def api_qa_reject("
        )
        out = out.replace("def api_qa_reject(", helper, 1)
        out = out.replace(
            'res = api_move(ref, new_status="build", note=full_note, board=board, caller_is_qa=True)',
            '_uncheck_mandatory_acceptance(path)\n    res = api_move(ref, new_status="build", note=full_note, board=board, caller_is_qa=True)',
            1,
        )
    return out


def patch_mcp_server(src: str) -> str:
    out = src
    if "import kb_cases" not in out and "import kb\n" in out:
        out = out.replace("import kb\n", "import kb\nimport kb_cases\nimport kb_history\n", 1)

    if '"kanban_case"' not in (out.split("WORK_TOOL_NAMES")[1].split(")")[0] if "WORK_TOOL_NAMES" in out else ""):
        out = out.replace(
            '    "kanban_qa",\n})',
            '    "kanban_qa",\n    "kanban_case",\n})',
            1,
        )
    return out


def patch_install_qa_lock(src: str) -> str:
    out = src
    desired_tools = (
        '                "tools:\\n"\n'
        '                "  - read_file\\n"\n'
        '                "  - write_file\\n"\n'
        '                "  - edit_file\\n"\n'
        '                "  - run_command\\n"\n'
    )
    if desired_tools in out:
        return out
    old_agy = (
        '                "subagent: true\\n"\n'
        '                "mainAgent: false\\n"\n'
        '                "model: inherit\\n"\n'
    )
    if old_agy in out:
        out = out.replace(old_agy, old_agy + desired_tools, 1)
    return out


def patch_viewer(src: str) -> str:
    out = src
    if "import kb_cases" not in out and "import kb_crud\n" in out:
        out = out.replace("import kb_crud\n", "import kb_crud\nimport kb_cases\nimport kb_history\n", 1)
    out = out.replace('"version": "2.6.0"', '"version": "3.0.0"')
    out = out.replace('KanbanViewer/2.6', 'KanbanViewer/3.0')
    out = out.replace(
        "kb_crud.purge_expired_retired(self.board)",
        "kb_crud.purge_expired_retired(self.board)\n        kb_cases.archive_stale_cases(self.board)",
    )
    if 'path == "/api/cases"' not in out and 'if path == "/api/ticket":' in out:
        routes = (
            'if path == "/api/cases":\n'
            '            return self._json(200, kb_cases.api_case_list(self.server.board, ticket=(qs.get("ticket") or [None])[0], project=(qs.get("project") or [None])[0]), head)\n\n'
            '        if path == "/api/case":\n'
            '            cid = (qs.get("id") or [""])[0].strip()\n'
            '            if not cid:\n'
            '                return self._json(400, {"ok": False, "error": "missing id"}, head)\n'
            '            try:\n'
            '                return self._json(200, kb_cases.api_case_show(cid, self.server.board), head)\n'
            '            except FileNotFoundError as e:\n'
            '                return self._json(404, {"ok": False, "error": str(e)}, head)\n\n'
            '        if path == "/api/history":\n'
            '            ref = (qs.get("ref") or [""])[0].strip()\n'
            '            if not ref:\n'
            '                return self._json(400, {"ok": False, "error": "missing ref"}, head)\n'
            '            return self._json(200, {"ok": True, "ref": ref, "history": kb_history.read_history(ref, self.server.board)}, head)\n\n'
            '        if path == "/api/ticket":'
        )
        out = out.replace('if path == "/api/ticket":', routes, 1)
    return out


def patch_board_ui(src: str) -> str:
    return (
        src.replace('"in-progress"', '"build"')
        .replace("'in-progress'", "'build'")
        .replace(".col-in-progress", ".col-build")
    )


def show_diff(path: Path, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path.relative_to(ROOT)}",
            tofile=f"b/{path.relative_to(ROOT)}",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Wire KanbanBoard v3.0 upgrades")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    targets = [
        (ROOT / "kb.py", patch_kb_py),
        (ROOT / "mcp_server.py", patch_mcp_server),
        (ROOT / "scripts" / "install_qa_lock.py", patch_install_qa_lock),
        (ROOT / "viewer.py", patch_viewer),
        (ROOT / "resources" / "board.css", patch_board_ui),
        (ROOT / "resources" / "board.js", patch_board_ui),
    ]
    for path, fn in targets:
        if not path.is_file():
            print(f"[SKIP] {path.relative_to(ROOT)} not found", file=sys.stderr)
            continue
        old = path.read_text(encoding="utf-8")
        new = fn(old)
        if old == new:
            print(f"[OK] {path.relative_to(ROOT)} already up to date.")
            continue
        print(show_diff(path, old, new))
        if args.apply:
            path.write_text(new, encoding="utf-8", newline="\n")
            print(f"[APPLIED] {path.relative_to(ROOT)}")

    dup_skill = ROOT / "skills" / "kanban-qa" / "SKILL.md"
    if dup_skill.is_file():
        if args.apply:
            dup_skill.unlink()
            print("[REMOVED] duplicate skills/kanban-qa/SKILL.md (agents/kb-qa.md is single source of truth)")
        else:
            print("[WOULD REMOVE] duplicate skills/kanban-qa/SKILL.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
