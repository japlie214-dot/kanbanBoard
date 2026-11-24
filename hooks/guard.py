#!/usr/bin/env python3
"""hooks/guard.py — Deterministic PreToolUse guard for Claude Code, Claude Desktop, and Antigravity.

Enforces three physical invariants:
  1. Only the 'kb-qa' subagent may invoke any kanban_qa MCP tool (Claude Code / Desktop).
  2. No agent may directly edit/write files inside the Kanban board directory, .qa_nonces, or .qa_secret.
  3. No agent may use shell commands (Bash / run_command) to tamper with board/, .qa_nonces, .qa_secret,
     or manually launch mcp_server.py --mode qa.
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
]

PROTECTED_CMD_PATTERNS = [
    (re.compile(r"mcp_server\.py[^\n]*--mode\s+qa", re.I), "Direct invocation of mcp_server.py --mode qa via shell is forbidden."),
    (re.compile(r"\bkb\.py\b[^\n]*\bqa[-_]?(?:start|approve|reject)\b", re.I), "QA approval via kb.py CLI is forbidden."),
    (re.compile(r"\.qa_nonces\b", re.I), "Reading or modifying .qa_nonces via shell is forbidden."),
    (re.compile(r"\.qa_secret\b", re.I), "Reading or modifying .qa_secret via shell is forbidden."),
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

    # Rule 1: Only kb-qa subagent may call kanban_qa
    if re.search(r"(?:^|__)kanban_qa$", tool_name):
        if agent_type != "kb-qa":
            caller = agent_type or "main-agent"
            return False, (
                f"BLOCKED: '{tool_name}' is restricted exclusively to the 'kb-qa' subagent "
                f"(caller='{caller}'). Spawn subagent_type='kb-qa' to audit and certify tickets."
            )
        return True, ""

    # Rule 2: Block direct file edits/reads on board/, .qa_nonces, .qa_secret
    if tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        target = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        if is_protected_path(target):
            return False, (
                f"BLOCKED: Direct file modification of '{target}' is forbidden. "
                "Use Kanban MCP tools for ticket state changes."
            )

    if tool_name == "Read":
        target = str(tool_input.get("file_path") or "")
        if re.search(r"(?:\.qa_nonces|\.qa_secret)", target, re.I):
            return False, f"BLOCKED: Reading QA secret/nonce path '{target}' is forbidden."

    # Rule 3: Block shell bypasses
    if tool_name == "Bash":
        cmd = str(tool_input.get("command") or "")
        reason = check_command(cmd)
        if reason:
            return False, f"BLOCKED: {reason}"

    return True, ""


def evaluate_antigravity(payload: dict) -> tuple[bool, str]:
    """Evaluate an Antigravity PreToolUse hook payload."""
    tc = payload.get("toolCall") or {}
    tool_name = str(tc.get("name") or "")
    args = tc.get("args") or {}

    if tool_name in {"write_to_file", "replace_file_content", "multi_replace_file_content"}:
        target = str(args.get("TargetFile") or "")
        if is_protected_path(target):
            return False, (
                f"BLOCKED: Direct file modification of '{target}' is forbidden. "
                "Use Kanban MCP tools for ticket state changes."
            )

    if tool_name == "view_file":
        target = str(args.get("AbsolutePath") or "")
        if re.search(r"(?:\.qa_nonces|\.qa_secret)", target, re.I):
            return False, f"BLOCKED: Reading QA secret/nonce path '{target}' is forbidden."

    if tool_name == "run_command":
        cmd = str(args.get("CommandLine") or "")
        reason = check_command(cmd)
        if reason:
            return False, f"BLOCKED: {reason}"

    if tool_name == "call_mcp_tool":
        mcp_tool = str(args.get("ToolName") or "")
        if mcp_tool == "kanban_qa":
            return False, (
                "BLOCKED: Direct invocation of kanban_qa by the main agent is forbidden. "
                "Only the independent kb-qa subagent may audit and approve tickets."
            )

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
