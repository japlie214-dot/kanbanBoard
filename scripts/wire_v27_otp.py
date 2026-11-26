#!/usr/bin/env python3
"""scripts/wire_v27_otp.py – Wires kb_qa_otp (unified MCP + auto-rotating qa_passkey) into mcp_server.py and scripts/install_qa_lock.py.

Usage:
  python scripts/wire_v27_otp.py --dry-run
  python scripts/wire_v27_otp.py --apply
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
    if "import kb_qa_otp" not in out and "import kb\n" in out:
        out = out.replace("import kb\n", "import kb\nimport kb_qa_otp\n", 1)

    # 1. Expose kanban_qa on unified WORK_TOOL_NAMES (gating via qa_passkey OTP)
    if '"kanban_qa"' not in out.split("WORK_TOOL_NAMES")[1].split(")")[0] if "WORK_TOOL_NAMES" in out else False:
        out = out.replace(
            '    "kanban_view",\n})',
            '    "kanban_view",\n    "kanban_qa",\n})',
            1,
        )

    # 2. Add qa_passkey property to kanban_qa schema
    if '"qa_passkey"' not in out:
        anchor = '"qa_nonce": {"type": "string"'
        if anchor in out:
            out = out.replace(
                anchor,
                '"qa_passkey": {"type": "string", "description": "Confidential single-use OTP from kb-qa system prompt (required)"},\n'
                '                "qa_nonce": {"type": "string"',
                1,
            )

    # 3. Enforce verify_passkey before kanban_qa dispatch (static-per-install passkey; manual rotate via install_qa_lock.py --rotate-key)
    if "kb_qa_otp.verify_passkey" not in out:
        qa_branch = 'elif name == "kanban_qa":'
        if qa_branch in out:
            guard_snippet = (
                f"{qa_branch}\n"
                '            otp = str(args.get("qa_passkey") or "").strip()\n'
                '            ok_otp, otp_err = kb_qa_otp.verify_passkey(otp)\n'
                '            if not ok_otp:\n'
                '                send_tool_result(req_id, otp_err, is_error=True)\n'
                '                return\n'
                '            if kb_qa_otp.contains_passkey_leak(str(args.get("note") or ""), otp):\n'
                '                send_tool_result(req_id, "FORBIDDEN: qa_passkey must never be echoed in note.", is_error=True)\n'
                '                return\n'
            )
            out = out.replace(qa_branch, guard_snippet, 1)

    return out


def patch_install_qa_lock(src: str) -> str:
    out = src
    if "import kb_qa_otp" not in out and "import sys\n" in out:
        out = out.replace(
            "import sys\nfrom pathlib import Path\n",
            "import sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).parent.parent.resolve()))\nimport kb_qa_otp\n",
            1,
        )
    if "--rotate-key" not in out and '"--install-git-hook"' in out:
        out = out.replace(
            '"--install-git-hook"',
            '"--rotate-key",\n        action="store_true",\n        help="Force-rotate ~/.kanban/.qa_passkey and re-inject into kb-qa.md",\n    )\n    parser.add_argument(\n        "--install-git-hook"',
            1,
        )
    if "ensure_and_inject_passkey" not in out and "def main():" in out:
        out = out.replace(
            "def main():",
            'def _sync_v27_passkey(force_rotate: bool = False):\n'
            '    _, updated = kb_qa_otp.ensure_and_inject_passkey(force_rotate=force_rotate)\n'
            '    print(f"[v2.7 OTP] qa_passkey synced into {len(updated)} kb-qa.md file(s) (secret redacted).")\n\n\n'
            "def main():",
            1,
        )
        out = re.sub(
            r'(\n[ \t]*print\("\\nDone!)',
            r'\n    _sync_v27_passkey(force_rotate=getattr(args, "rotate_key", False))\1',
            out,
            count=1,
        )
    return out


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
    parser = argparse.ArgumentParser(description="Wire v2.7 auto-rotating qa_passkey OTP")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    targets = [
        (ROOT / "mcp_server.py", patch_mcp_server),
        (ROOT / "scripts" / "install_qa_lock.py", patch_install_qa_lock),
    ]
    for path, fn in targets:
        if not path.is_file():
            print(f"[SKIP] {path} not found", file=sys.stderr)
            continue
        old = path.read_text(encoding="utf-8")
        new = fn(old)
        if old == new:
            print(f"[OK] {path.relative_to(ROOT)} already wired.")
            continue
        print(show_diff(path, old, new))
        if args.apply:
            path.write_text(new, encoding="utf-8", newline="\n")
            print(f"[APPLIED] {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
