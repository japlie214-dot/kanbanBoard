"""tests/test_v27_qa_otp.py – Positive & Negative (Pluto) tests for v2.7 Prompt-Injected Auto-Rotating qa_passkey."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import hooks.guard as guard
import kb_qa_otp


class TestQaPasskeyAutoRotate(unittest.TestCase):
    def test_generate_verify_and_single_use_rotation(self):
        with tempfile.TemporaryDirectory() as td:
            pfile = Path(td) / ".qa_passkey"
            claude_agent = Path(td) / "claude_kb-qa.md"
            agy_agent = Path(td) / "agy_kb-qa.md"
            template = "---\nname: kb-qa\n---\n# QA\nQA_PASSKEY: __QA_PASSKEY__\n"
            claude_agent.write_text(template, encoding="utf-8")
            agy_agent.write_text(template, encoding="utf-8")

            old_env_file = os.environ.get("KANBAN_QA_PASSKEY_FILE")
            old_env_targets = os.environ.get("KANBAN_QA_AGENT_TARGETS")
            os.environ["KANBAN_QA_PASSKEY_FILE"] = str(pfile)
            os.environ["KANBAN_QA_AGENT_TARGETS"] = os.pathsep.join([str(claude_agent), str(agy_agent)])
            try:
                key1, updated1 = kb_qa_otp.ensure_and_inject_passkey()
                self.assertEqual(len(updated1), 2)
                self.assertEqual(len(key1), 8)
                self.assertTrue(key1.isalnum())
                self.assertIn(f"QA_PASSKEY: {key1}", claude_agent.read_text(encoding="utf-8"))
                self.assertIn(f"QA_PASSKEY: {key1}", agy_agent.read_text(encoding="utf-8"))

                # Positive: valid key passes
                ok, err = kb_qa_otp.verify_passkey(key1)
                self.assertTrue(ok, err)

                # Negative (Pluto): missing / forged key rejected
                self.assertFalse(kb_qa_otp.verify_passkey("")[0])
                self.assertFalse(kb_qa_otp.verify_passkey("kbqa_wrong_guess")[0])

                # Leak detection
                self.assertTrue(kb_qa_otp.contains_passkey_leak(f"oops {key1}", key1))
                self.assertFalse(kb_qa_otp.contains_passkey_leak("clean QA note", key1))

                # Auto-rotate after approve/reject: key1 immediately dies, key2 injected into both hosts!
                key2, updated2 = kb_qa_otp.rotate_passkey()
                self.assertEqual(len(updated2), 2)
                self.assertNotEqual(key1, key2)
                self.assertFalse(kb_qa_otp.verify_passkey(key1)[0])
                self.assertTrue(kb_qa_otp.verify_passkey(key2)[0])
                self.assertIn(f"QA_PASSKEY: {key2}", claude_agent.read_text(encoding="utf-8"))
                self.assertIn(f"QA_PASSKEY: {key2}", agy_agent.read_text(encoding="utf-8"))
                self.assertNotIn(key1, claude_agent.read_text(encoding="utf-8"))
            finally:
                if old_env_file is None:
                    os.environ.pop("KANBAN_QA_PASSKEY_FILE", None)
                else:
                    os.environ["KANBAN_QA_PASSKEY_FILE"] = old_env_file
                if old_env_targets is None:
                    os.environ.pop("KANBAN_QA_AGENT_TARGETS", None)
                else:
                    os.environ["KANBAN_QA_AGENT_TARGETS"] = old_env_targets


class TestGuardBlocksPasskeyAndKbQaReads(unittest.TestCase):
    def test_claude_blocks_reading_kb_qa_md_and_passkey(self):
        for target in [
            "C:/Users/dev/.claude/agents/kb-qa.md",
            "C:/Users/dev/.gemini/config/agents/kb-qa.md",
            "C:/Users/dev/.kanban/.qa_passkey",
            "C:/Projects/kanbanBoard/agents/kb-qa.md",
        ]:
            ok, reason = guard.evaluate_claude({"tool_name": "Read", "tool_input": {"file_path": target}})
            self.assertFalse(ok, f"Expected Claude Read to block {target}")
            self.assertIn("BLOCKED", reason)

    def test_antigravity_blocks_viewing_kb_qa_md_and_passkey(self):
        for target in [
            "C:/Users/dev/.gemini/config/agents/kb-qa.md",
            "C:/Users/dev/.kanban/.qa_passkey",
        ]:
            ok, reason = guard.evaluate_antigravity({
                "toolCall": {"name": "view_file", "args": {"AbsolutePath": target}}
            })
            self.assertFalse(ok, f"Expected Antigravity view_file to block {target}")
            self.assertIn("BLOCKED", reason)

    def test_shell_blocks_cat_or_type_on_kb_qa_md_and_passkey(self):
        for cmd in [
            "cat ~/.gemini/config/agents/kb-qa.md",
            "type C:\\Users\\dev\\.kanban\\.qa_passkey",
            "Get-Content ~/.claude/agents/kb-qa.md",
        ]:
            self.assertIsNotNone(guard.check_command(cmd), f"Expected shell command blocked: {cmd}")

    def test_claude_still_enforces_agent_type_on_kanban_qa(self):
        self.assertFalse(guard.evaluate_claude({
            "tool_name": "mcp__kanban__kanban_qa",
            "tool_input": {"action": "approve"},
            "agent_type": "",
        })[0])
        self.assertTrue(guard.evaluate_claude({
            "tool_name": "mcp__kanban__kanban_qa",
            "tool_input": {"action": "approve"},
            "agent_type": "kb-qa",
        })[0])

    def test_kb_qa_md_has_no_restrictive_tools_allowlist(self):
        p = ROOT / "agents" / "kb-qa.md"
        if p.is_file():
            txt = p.read_text(encoding="utf-8")
            self.assertNotIn("\ntools:", txt)
            self.assertIn("disallowedTools: Edit, MultiEdit, NotebookEdit", txt)
            self.assertIn("model: claude-haiku-5-5", txt)
            self.assertIn("effort: medium", txt)
            self.assertNotIn("autoCompactWindow", txt)
            self.assertIn("QA_PASSKEY: __QA_PASSKEY__", txt)

    def test_install_qa_lock_renders_antigravity_subagent_frontmatter(self):
        import scripts.install_qa_lock as iql
        sec = Path("C:/Users/dev/.kanban/.qa_secret")
        claude_txt = iql.render_kb_qa_agent(sec, platform="claude")
        agy_txt = iql.render_kb_qa_agent(sec, platform="antigravity")
        self.assertIn("model: claude-haiku-5-5", claude_txt)
        self.assertNotIn("subagent: true", claude_txt)
        self.assertIn("subagent: true", agy_txt)
        self.assertIn("mainAgent: false", agy_txt)
        self.assertIn("model: inherit", agy_txt)
        self.assertIn("read_file", agy_txt)
        self.assertIn("write_file", agy_txt)
        self.assertIn("edit_file", agy_txt)
        self.assertIn("run_command", agy_txt)
        self.assertNotIn("call_mcp_tool", agy_txt)
        self.assertIn("QA_PASSKEY: __QA_PASSKEY__", agy_txt)


if __name__ == "__main__":
    unittest.main()
