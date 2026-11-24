#!/usr/bin/env python3
"""scripts/install_qa_lock.py — Cross-platform installer for KanbanBoard physical QA isolation.

Performs 4 steps:
  1. Generates ~/.kanban/.qa_secret (32 random bytes, hex) with restricted file permissions if absent.
  2. Installs kb-qa.md with resolved absolute paths into:
       - ~/.claude/agents/kb-qa.md   (Claude Code & Claude Desktop local Code sessions)
       - ~/.gemini/config/agents/kb-qa.md (Antigravity CLI / App / IDE)
  3. Merges the Antigravity PreToolUse guard into ~/.gemini/config/hooks.json without overwriting existing hooks.
  4. Optionally installs scripts/pre_commit_verify_done.py into .git/hooks/pre-commit (--install-git-hook).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
MCP_SERVER = (REPO_ROOT / "mcp_server.py").resolve()
GUARD_SCRIPT = (REPO_ROOT / "hooks" / "guard.py").resolve()
KB_QA_TEMPLATE = REPO_ROOT / "agents" / "kb-qa.md"


def ensure_qa_secret() -> Path:
    sec_dir = Path.home() / ".kanban"
    sec_dir.mkdir(parents=True, exist_ok=True)
    sec_file = sec_dir / ".qa_secret"
    if not sec_file.exists():
        sec_file.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")
        if os.name == "nt":
            user = os.environ.get("USERNAME", "")
            if user:
                subprocess.run(
                    ["icacls", str(sec_file), "/inheritance:r", "/grant:r", f"{user}:(R,W)"],
                    capture_output=True,
                )
        else:
            os.chmod(sec_file, stat.S_IRUSR | stat.S_IWUSR)
        print(f"[OK] Generated QA signing secret: {sec_file}")
    else:
        print(f"[OK] Existing QA signing secret preserved: {sec_file}")
    return sec_file


def render_kb_qa_agent(sec_file: Path) -> str:
    text = KB_QA_TEMPLATE.read_text(encoding="utf-8")
    mcp_posix = MCP_SERVER.as_posix()
    text = text.replace("C:/Projects/kanbanBoard/mcp_server.py", mcp_posix)
    if "KANBAN_QA_SECRET_FILE" not in text:
        text = text.replace(
            '      KANBAN_REQUIRE_QA_SIGNATURE: "1"',
            f'      KANBAN_REQUIRE_QA_SIGNATURE: "1"\n      KANBAN_QA_SECRET_FILE: "{sec_file.as_posix()}"',
        )
    return text


def install_agents(sec_file: Path):
    rendered = render_kb_qa_agent(sec_file)
    targets = [
        Path.home() / ".claude" / "agents" / "kb-qa.md",
        Path.home() / ".gemini" / "config" / "agents" / "kb-qa.md",
    ]
    for dst in targets:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"[OK] Installed kb-qa subagent: {dst}")


def install_antigravity_hook():
    hooks_path = Path.home() / ".gemini" / "config" / "hooks.json"
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if hooks_path.exists():
        try:
            existing = json.loads(hooks_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = hooks_path.with_suffix(".json.bak")
            shutil.copy2(hooks_path, backup)
            print(f"[WARN] Backed up malformed hooks.json to {backup}")
            existing = {}

    existing["kanban-qa-guard"] = {
        "enabled": True,
        "PreToolUse": [
            {
                "matcher": "write_to_file|replace_file_content|multi_replace_file_content|view_file|run_command",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'"{sys.executable}" "{GUARD_SCRIPT.as_posix()}" --client antigravity',
                        "timeout": 10,
                    }
                ],
            }
        ],
    }
    hooks_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"[OK] Merged Antigravity PreToolUse guard into: {hooks_path}")


def install_git_hook(target_repo: Path):
    git_hooks = target_repo / ".git" / "hooks"
    if not git_hooks.is_dir():
        print(f"[SKIP] No .git/hooks directory found in {target_repo}")
        return
    dst = git_hooks / "pre-commit"
    hook_body = (
        "#!/usr/bin/env sh\n"
        f'"{sys.executable}" "{(REPO_ROOT / "scripts" / "pre_commit_verify_done.py").as_posix()}"\n'
    )
    dst.write_text(hook_body, encoding="utf-8", newline="\n")
    if os.name != "nt":
        os.chmod(dst, 0o755)
    print(f"[OK] Installed git pre-commit hook: {dst}")


def main():
    parser = argparse.ArgumentParser(description="Install KanbanBoard QA physical isolation lock")
    parser.add_argument(
        "--install-git-hook",
        default=None,
        help="Optional target git repo path to install pre-commit HMAC verification hook",
    )
    args = parser.parse_args()

    sec_file = ensure_qa_secret()
    install_agents(sec_file)
    install_antigravity_hook()
    if args.install_git_hook:
        install_git_hook(Path(args.install_git_hook).resolve())

    print("\nDone! Restart Claude Code / Claude Desktop / Antigravity to load the isolated kb-qa subagent and hooks.")


if __name__ == "__main__":
    main()
