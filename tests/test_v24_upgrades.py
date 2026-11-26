"""tests/test_v24_upgrades.py – Positive & Negative discriminator tests for KanbanBoard v2.4 upgrades."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import hooks.guard as guard
import kb_ergonomics


class TestPhase1SecurityGuard(unittest.TestCase):
    def test_claude_blocks_non_qa_calling_kanban_qa(self):
        ok, reason = guard.evaluate_claude({
            "tool_name": "mcp__kanban-qa__kanban_qa",
            "tool_input": {"action": "approve"},
            "agent_type": "",
        })
        self.assertFalse(ok)
        self.assertIn("kb-qa", reason)

    def test_claude_allows_kb_qa_calling_kanban_qa(self):
        ok, _ = guard.evaluate_claude({
            "tool_name": "mcp__kanban-qa__kanban_qa",
            "tool_input": {"action": "start"},
            "agent_type": "kb-qa",
        })
        self.assertTrue(ok)

    def test_blocks_human_approve_spoofing_via_curl_or_python(self):
        for cmd in [
            "curl -X POST http://127.0.0.1:7890/api/ticket/manual-approve -d '{}'",
            "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:7890/api/ticket/manual-approve')\"",
            "python -c \"import kb; kb.api_manual_approve('a/b/T1','me','reason12345', kb.board_root())\"",
        ]:
            reason = guard.check_command(cmd)
            self.assertIsNotNone(reason, f"Expected command to be blocked: {cmd}")

    def test_antigravity_does_not_leak_passkey_via_file_or_shell(self):
        # Antigravity PreToolUse blocks reading .qa_passkey and kb-qa.md via view_file, read_file, or run_command
        for path in ["C:/Users/dev/.kanban/.qa_passkey", "C:/Users/dev/.gemini/config/agents/kb-qa.md"]:
            ok, reason = guard.evaluate_antigravity({
                "toolCall": {"name": "read_file", "args": {"Path": path}}
            })
            self.assertFalse(ok, f"Expected read_file blocked for {path}")
            self.assertIn("BLOCKED", reason)
        self.assertIsNotNone(guard.check_command("type C:\\Users\\dev\\.kanban\\.qa_passkey"))

    def test_plugin_json_does_not_leak_kanban_qa(self):
        pj = ROOT / ".claude-plugin" / "plugin.json"
        if pj.is_file():
            data = json.loads(pj.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", {})
            self.assertIn("kanban", servers)
            self.assertNotIn("kanban-qa", servers)


class TestPhase2Ergonomics(unittest.TestCase):
    def test_build_plan_from_plain_strings(self):
        md = kb_ergonomics.build_plan_from_steps(["Implement fix", "Run unit tests"], tier="quick")
        self.assertIn("- [ ] S1 [START] Implement fix", md)
        self.assertIn("- [ ] S2 [after:S1] [ACCEPTANCE:MANDATORY] Run unit tests", md)

    def test_build_plan_rejects_empty_steps(self):
        with self.assertRaises(ValueError):
            kb_ergonomics.build_plan_from_steps([])

    def test_gate2_allows_research_and_docs_without_dirty_git(self):
        with tempfile.TemporaryDirectory() as td:
            ok, _ = kb_ergonomics.has_verifiable_work(td, {"type": "research"})
            self.assertTrue(ok)
            ok2, reason2 = kb_ergonomics.has_verifiable_work(td, {"type": "feature"})
            self.assertFalse(ok2)
            self.assertIn("Gate 2 rejected", reason2)

    def test_reap_expired_leases(self):
        now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
        tickets = [
            {"ref": "a/b/T1", "lease_expires": (now - timedelta(minutes=10)).isoformat()},
            {"ref": "a/b/T2", "lease_expires": (now + timedelta(minutes=30)).isoformat()},
        ]
        res = kb_ergonomics.reap_expired_leases(tickets, now=now)
        self.assertTrue(res[0]["lease_expired"])
        self.assertFalse(res[1]["lease_expired"])

    def test_compact_qa_evidence_positive_and_negative(self):
        good = """# QA Evidence: a/b/T1
## Ponytail Diff
Minimal 12-line change, no bloat.
## Positive Tests
pytest passed (exit 0).
## Negative Discriminator
Invalid input rejected with 400 (Pluto check passed).
Verdict: PASS
"""
        ok, missing = kb_ergonomics.validate_qa_evidence(good)
        self.assertTrue(ok, f"Unexpected missing: {missing}")

        bad_no_neg = """# QA Evidence: a/b/T1
## Ponytail Diff
Clean.
## Positive Tests
Passed.
Verdict: PASS
"""
        ok2, missing2 = kb_ergonomics.validate_qa_evidence(bad_no_neg)
        self.assertFalse(ok2)
        self.assertIn("Negative Discriminator", missing2)


class TestPhase3FrontmatterAndLogo(unittest.TestCase):
    def test_kb_qa_frontmatter_haiku_medium_no_autocompact(self):
        p = ROOT / "agents" / "kb-qa.md"
        if p.is_file():
            txt = p.read_text(encoding="utf-8")
            self.assertTrue(txt.startswith("---\n"))
            self.assertIn("model: claude-haiku-5-5", txt)
            self.assertIn("effort: medium", txt)
            self.assertNotIn("autoCompactWindow", txt)
            self.assertNotIn("subagent: true", txt)
            self.assertNotIn("mainAgent: false", txt)

    def test_kanban_qa_skill_yaml_quoted_and_model_disabled(self):
        p = ROOT / "skills" / "kanban-qa" / "SKILL.md"
        if p.is_file():
            txt = p.read_text(encoding="utf-8")
            self.assertTrue(txt.startswith("---\n"))
            self.assertIn('description: "', txt)
            self.assertIn("disable-model-invocation: true", txt)

    def test_concept_b_logo_svg(self):
        svg = ROOT / "assets" / "logo.svg"
        if svg.is_file():
            txt = svg.read_text(encoding="utf-8")
            self.assertIn("#1D4ED8", txt)
            self.assertIn("#34D399", txt)


if __name__ == "__main__":
    unittest.main()
