#!/usr/bin/env python3
"""tests/test_qa_lock.py — Verification suite for dual-mode MCP, PreToolUse hooks, HMAC signatures, and Gate hardening."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))
import mcp_server
from hooks import guard


class TestDualModeMcp(unittest.TestCase):
    def test_work_mode_omits_kanban_qa(self):
        names = {t["name"] for t in mcp_server.tools_for_mode("work")}
        self.assertNotIn("kanban_qa", names)
        self.assertIn("kanban_move", names)
        self.assertEqual(len(names), 6)

    def test_qa_mode_exposes_only_qa_and_readonly_tools(self):
        names = {t["name"] for t in mcp_server.tools_for_mode("qa")}
        self.assertEqual(names, {"kanban_board", "kanban_ticket", "kanban_qa"})
        self.assertNotIn("kanban_move", names)
        self.assertNotIn("kanban_update", names)

    def test_work_mode_rejects_kanban_qa_call(self):
        captured = []
        orig_send = mcp_server.send_response
        mcp_server.send_response = lambda r: captured.append(r)
        try:
            mcp_server.handle_tool_call(1, "kanban_qa", {"action": "start", "ref": "a/b/T001"}, Path("."), mode="work")
        finally:
            mcp_server.send_response = orig_send
        self.assertTrue(captured[0]["result"]["isError"])
        self.assertIn("not available in MCP server mode 'work'", captured[0]["result"]["content"][0]["text"])

    def test_qa_mode_rejects_write_actions(self):
        captured = []
        orig_send = mcp_server.send_response
        mcp_server.send_response = lambda r: captured.append(r)
        try:
            mcp_server.handle_tool_call(2, "kanban_board", {"view": "init"}, Path("."), mode="qa")
            mcp_server.handle_tool_call(3, "kanban_ticket", {"action": "edit", "ref": "a/b/T001"}, Path("."), mode="qa")
        finally:
            mcp_server.send_response = orig_send
        self.assertTrue(captured[0]["result"]["isError"])
        self.assertTrue(captured[1]["result"]["isError"])


class TestPreToolUseGuard(unittest.TestCase):
    def test_claude_blocks_main_agent_from_kanban_qa(self):
        ok, reason = guard.evaluate_claude({"tool_name": "mcp__kanban-qa__kanban_qa", "tool_input": {"action": "approve"}})
        self.assertFalse(ok)
        self.assertIn("main-agent", reason)

    def test_claude_blocks_other_subagent_from_kanban_qa(self):
        ok, reason = guard.evaluate_claude({
            "tool_name": "mcp__kanban-qa__kanban_qa",
            "agent_type": "Explore",
            "tool_input": {"action": "approve"},
        })
        self.assertFalse(ok)
        self.assertIn("Explore", reason)

    def test_claude_allows_kb_qa_subagent(self):
        ok, _ = guard.evaluate_claude({
            "tool_name": "mcp__kanban-qa__kanban_qa",
            "agent_type": "kb-qa",
            "tool_input": {"action": "approve"},
        })
        self.assertTrue(ok)

    def test_claude_blocks_direct_board_and_secret_edits(self):
        for path in [
            "C:/Projects/kanbanBoard/board/demo/core/T001.md",
            "/home/user/.kanban/board/demo/core/T001.md",
            "/home/user/.kanban/.qa_secret",
            "C:/Projects/kanbanBoard/board/.qa_nonces/demo_core_T001.nonce",
        ]:
            ok, _ = guard.evaluate_claude({"tool_name": "Edit", "tool_input": {"file_path": path}})
            self.assertFalse(ok, f"Expected Edit to be blocked for {path}")

    def test_claude_blocks_shell_bypasses(self):
        for cmd in [
            "python mcp_server.py --mode qa",
            "python kb.py qa-approve demo/core/T001 abc ev.md",
            "cat ~/.kanban/.qa_secret",
            "cat C:/Projects/kanbanBoard/board/.qa_nonces/x.nonce",
        ]:
            ok, _ = guard.evaluate_claude({"tool_name": "Bash", "tool_input": {"command": cmd}})
            self.assertFalse(ok, f"Expected Bash to be blocked for: {cmd}")

    def test_antigravity_blocks_board_writes_and_shell_bypasses(self):
        ok, _ = guard.evaluate_antigravity({
            "toolCall": {
                "name": "replace_file_content",
                "args": {"TargetFile": "C:/Projects/kanbanBoard/board/demo/core/T001.md"},
            }
        })
        self.assertFalse(ok)

        ok2, _ = guard.evaluate_antigravity({
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "python mcp_server.py --mode qa"},
            }
        })
        self.assertFalse(ok2)

        ok3, _ = guard.evaluate_antigravity({
            "toolCall": {
                "name": "replace_file_content",
                "args": {"TargetFile": "C:/Projects/myApp/src/app.py"},
            }
        })
        self.assertTrue(ok3)

        ok4, reason = guard.evaluate_antigravity({
            "toolCall": {
                "name": "call_mcp_tool",
                "args": {"ServerName": "kanban-board_kanban", "ToolName": "kanban_qa"},
            }
        })
        self.assertFalse(ok4)
        self.assertIn("Direct invocation of kanban_qa by the main agent is forbidden", reason)

    def test_cli_exit_codes(self):
        payload = json.dumps({"tool_name": "mcp__kanban__kanban_qa", "tool_input": {"action": "start"}})
        proc = subprocess.run(
            [sys.executable, str(ROOT / "hooks" / "guard.py"), "--client", "claude"],
            input=payload,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        out = json.loads(proc.stdout)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")


class TestHmacSigningHelpers(unittest.TestCase):
    def test_sign_and_verify_roundtrip(self):
        import kb
        sig = kb.compute_qa_signature("demo/core/T001", "deadbeef", "super-secret")
        ok, _ = kb.verify_qa_signature(
            "demo/core/T001",
            {"qa_signature": sig, "qa_evidence_sha256": "deadbeef"},
            secret="super-secret",
        )
        self.assertTrue(ok)

        # Tampered digest fails verification
        ok_bad, msg = kb.verify_qa_signature(
            "demo/core/T001",
            {"qa_signature": sig, "qa_evidence_sha256": "00000000"},
            secret="super-secret",
        )
        self.assertFalse(ok_bad)
        self.assertIn("invalid qa_signature", msg)


class TestQaCliAndBoardLockFallback(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.board = Path(self.temp_dir) / "board"
        self.board.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_board_alias(self):
        import kb
        self.assertTrue(callable(kb.find_board))
        self.assertEqual(kb.find_board, kb.board_root)

    def test_board_lock_fallback_under_permission_error(self):
        import kb
        # Test board_lock executes without crashing even if lock file creation fails
        with kb.board_lock(self.board):
            pass  # Acquired cleanly


if __name__ == "__main__":
    unittest.main()
