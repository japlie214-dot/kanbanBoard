#!/usr/bin/env python3
"""hooks/guard.py – Deterministic PreToolUse guard for Claude Code, Claude Desktop, and Antigravity (v2.7).

Enforces three physical invariants:
  1. Claude Code / Desktop: only the 'kb-qa' subagent (`agent_type == "kb-qa"`) may invoke `kanban_qa`.
  2. Both Claude & Antigravity: NO agent may read or modify protected Kanban paths (`board/`, `.qa_nonces`,
     `.qa_secret`, `.qa_passkey`, or `kb-qa.md`), so only the host-spawned `kb-qa` subagent holds `QA_PASSKEY`.
  3. No agent may use shell commands (`Bash` / `run_command`) to tamper with `board/`, secrets/passkeys,
     `kb-qa.md`, `kb.py qa`, or spoof human approval on port `7890`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

PROTECTED_PATH_PATTERNS = [
    re.compile(r"(?:^|[\\/])kanbanboard[\\/]board(?:[\\/]|$)", re.I),
    re.compile(r"(?:^|[\\/])\.kanban[\\/]board(?:[\\/]|$)", re.I),
    re.compile(r"(?:^|[\\/])\.qa_nonces(?:[\\/]|$)", re.I),
    re.compile(r"(?:^|[\\/])\.qa_secret$", re.I),
    re.compile(r"(?:^|[\\/])\.qa_passkey$", re.I),
    re.compile(r"(?:^|[\\/])agents[\\/]kb-qa\.md$", re.I),
]

PROTECTED_READ_PATTERNS = [
    re.compile(r"(?:\.qa_nonces|\.qa_secret|\.qa_passkey)", re.I),
    re.compile(r"(?:^|[\\/])agents[\\/]kb-qa\.md$", re.I),
]

PROTECTED_CMD_PATTERNS = [
    (re.compile(r"mcp_server\.py[^\n]*--mode\s+qa", re.I), "Direct invocation of mcp_server.py --mode qa via shell is forbidden."),
    (re.compile(r"\bkb\.py\b[^\n]*\bqa[_-]?(?:start|approve|reject)\b", re.I), "QA approval via kb.py CLI is forbidden."),
    (re.compile(r"\bapi_(?:manual_approve|qa_(?:start|approve|reject))\b", re.I), "Direct invocation of QA or manual approval Python APIs via shell is forbidden."),
    (re.compile(r"(?:127\.0\.0\.1|localhost):789\d|manual[-_]?approve", re.I), "Calling the human web viewer approval endpoint via shell is forbidden."),
    (re.compile(r"\.qa_nonces\b", re.I), "Reading or modifying .qa_nonces via shell is forbidden."),
    (re.compile(r"\.qa_secret\b", re.I), "Reading or modifying .qa_secret via shell is forbidden."),
    (re.compile(r"\.qa_passkey\b", re.I), "Reading or modifying .qa_passkey via shell is forbidden."),
    (re.compile(r"\b(?:load_passkey|ensure_and_inject_passkey|rotate_passkey)\b", re.I), "Direct invocation of kb_qa_otp passkey helpers via shell is forbidden."),
    (re.compile(r"kb-qa\.md\b", re.I), "Reading or modifying kb-qa.md via shell is forbidden (protects QA_PASSKEY OTP)."),
    (re.compile(r"(?:kanbanboard[\\/]board|\.kanban[\\/]board)", re.I), "Direct shell access to the centralized Kanban board directory is forbidden; use Kanban MCP tools."),
]


def _extra_protected_board_root() -> str:
    env_board = os.environ.get("KANBAN_BOARD_ROOT", "").strip()
    return env_board.replace("\\", "/").rstrip("/").lower() if env_board else ""


def is_protected_path(raw_path: str) -> bool:
    if not raw_path:
        return False
    norm = raw_path.replace("\\", "/")
    extra = _extra_protected_board_root()
    if extra and (norm.lower() == extra or norm.lower().startswith(extra + "/")):
        return True
    return any(p.search(norm) for p in PROTECTED_PATH_PATTERNS)


def is_protected_read_path(raw_path: str) -> bool:
    if not raw_path:
        return False
    norm = raw_path.replace("\\", "/")
    return any(p.search(norm) for p in PROTECTED_READ_PATTERNS)


def check_command(cmd: str) -> str | None:
    if not cmd:
        return None
    for pat, reason in PROTECTED_CMD_PATTERNS:
        if pat.search(cmd):
            return reason
    extra = _extra_protected_board_root()
    if extra and extra in cmd.replace("\\", "/").lower():
        return "Direct shell access to KANBAN_BOARD_ROOT is forbidden; use Kanban MCP tools."
    return None


def evaluate_claude(payload: dict) -> tuple[bool, str]:
    """Evaluate a Claude Code / Claude Desktop PreToolUse hook payload."""
    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    agent_type = str(payload.get("agent_type") or "").strip()

    # Rule 1: Only kb-qa subagent may call kanban_qa (defense-in-depth alongside qa_passkey)
    if re.search(r"(?:^|__)kanban_qa$", tool_name):
        if agent_type != "kb-qa":
            caller = agent_type or "main-agent"
            return False, (
                f"BLOCKED: '{tool_name}' is restricted exclusively to the 'kb-qa' subagent "
                f"(caller='{caller}'). Spawn subagent_type='kb-qa' to audit and certify tickets."
            )
        return True, ""

    # Rule 2: Block direct file edits/reads on board/, secrets, passkey, and kb-qa.md
    if tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        target = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        if is_protected_path(target):
            return False, (
                f"BLOCKED: Direct file modification of '{target}' is forbidden. "
                "Use Kanban MCP tools for ticket state changes."
            )

    if tool_name == "Read":
        target = str(tool_input.get("file_path") or "")
        if is_protected_read_path(target):
            return False, f"BLOCKED: Reading protected QA secret/agent path '{target}' is forbidden."

    # Rule 3: Block shell bypasses
    if tool_name == "Bash":
        cmd = str(tool_input.get("command") or "")
        reason = check_command(cmd)
        if reason:
            return False, f"BLOCKED: {reason}"

    return True, ""


def evaluate_antigravity(payload: dict) -> tuple[bool, str]:
    """Evaluate an Antigravity PreToolUse hook payload.

    In v2.7, `kanban_qa` is enforced cryptographically inside `mcp_server.py` via the
    auto-rotating 144-bit `qa_passkey` injected solely into `~/.gemini/config/agents/kb-qa.md`.
    This hook guarantees no Antigravity agent can read `kb-qa.md`, `.qa_passkey`, `.qa_secret`,
    `.qa_nonces`, or tamper with `board/` or port 7890.
    """
    tc = payload.get("toolCall") or {}
    tool_name = str(tc.get("name") or "")
    args = tc.get("args") or {}

    if tool_name in {"write_to_file", "replace_file_content", "multi_replace_file_content", "write_file", "edit_file"}:
        target = str(args.get("TargetFile") or args.get("Path") or "")
        if is_protected_path(target):
            return False, (
                f"BLOCKED: Direct file modification of '{target}' is forbidden. "
                "Use Kanban MCP tools for ticket state changes."
            )

    if tool_name in {"view_file", "read_file"}:
        target = str(args.get("AbsolutePath") or args.get("Path") or "")
        if is_protected_read_path(target):
            return False, f"BLOCKED: Reading protected QA secret/agent path '{target}' is forbidden."

    if tool_name == "run_command":
        cmd = str(args.get("CommandLine") or "")
        reason = check_command(cmd)
        if reason:
            return False, f"BLOCKED: {reason}"

    return True, ""


def main():
    parser = argparse.ArgumentParser(description="Kanban PreToolUse Security Guard")
    parser.add_argument("--client", choices=["claude", "antigravity"], required=True)
    args = parser.parse_args()

    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    if args.client == "claude":
        allowed, reason = evaluate_claude(payload)
        if not allowed:
            out = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
            sys.stdout.write(json.dumps(out) + "\n")
            sys.exit(2)
        sys.exit(0)
    else:
        allowed, reason = evaluate_antigravity(payload)
        if not allowed:
            sys.stdout.write(json.dumps({"decision": "deny", "reason": reason}) + "\n")
        else:
            sys.stdout.write(json.dumps({"decision": "allow"}) + "\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
