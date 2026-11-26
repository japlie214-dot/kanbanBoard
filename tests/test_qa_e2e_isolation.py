#!/usr/bin/env python3
"""tests/test_qa_e2e_isolation.py
Rigorous End-to-End Test proving:
1. ONLY kb-qa can move a ticket to done
2. Main agents and non-kb-qa subagents CANNOT move tickets to done
3. The complete lifecycle from backlog -> in-progress -> verify -> done (via kb-qa)
4. Ephemeral single-use nonce cannot be reused
5. Pre-commit verify-done verifies cryptographic HMAC signature
"""
from __future__ import annotations

import hashlib
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
import kb
import kb_qa_otp
import mcp_server
from hooks import guard


class TestOnlyKbQaCanMoveTicketToDone(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="kb_qa_e2e_"))
        self.board = self.temp_dir / "board"
        self.workspace = self.temp_dir / "workspace"
        self.workspace.mkdir(parents=True)

        # Isolate OTP passkey & agent target files inside temp_dir
        self._old_passkey_file = os.environ.get("KANBAN_QA_PASSKEY_FILE")
        self._old_agent_targets = os.environ.get("KANBAN_QA_AGENT_TARGETS")
        self.passkey_file = self.temp_dir / ".qa_passkey"
        self.agent_md = self.temp_dir / "kb-qa.md"
        self.agent_md.write_text("---\nname: kb-qa\n---\nQA_PASSKEY: __QA_PASSKEY__\n", encoding="utf-8")
        os.environ["KANBAN_QA_PASSKEY_FILE"] = str(self.passkey_file)
        os.environ["KANBAN_QA_AGENT_TARGETS"] = str(self.agent_md)
        self.passkey, _ = kb_qa_otp.ensure_and_inject_passkey()

        # Initialize git workspace
        subprocess.run(["git", "-C", str(self.workspace), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "config", "user.name", "Tester"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "config", "user.email", "test@domain.local"], check=True)

        # Initialize board
        kb.api_init("demo", "feature", self.board)
        self.secret = "e2e-super-secret-key-12345"
        os.environ["KANBAN_QA_SECRET"] = self.secret

        # Create ticket
        dag = (
            "- [ ] M1. [START] Core business logic\n"
            "  - [ ] M2. [after:M1] [ACCEPTANCE:MANDATORY] Unit & integration tests pass\n"
        )
        res = kb.api_create("demo/feature", "E2E Isolation Ticket", self.board, plan=dag)
        self.ref = res["ref"]
        kb.api_ticket_edit(
            self.ref,
            board=self.board,
            outcome="Observable requirement met.",
            scope="Allowed surfaces: logic.py",
            prove="python -c 'import logic'",
        )

    def tearDown(self):
        if self._old_passkey_file is None:
            os.environ.pop("KANBAN_QA_PASSKEY_FILE", None)
        else:
            os.environ["KANBAN_QA_PASSKEY_FILE"] = self._old_passkey_file
        if self._old_agent_targets is None:
            os.environ.pop("KANBAN_QA_AGENT_TARGETS", None)
        else:
            os.environ["KANBAN_QA_AGENT_TARGETS"] = self._old_agent_targets
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_main_agent_cannot_move_to_done_via_kanban_move(self):
        """Author / main agent cannot transition a ticket to done via kanban_move."""
        # Move backlog -> in-progress
        kb.api_move(self.ref, "in-progress", "Dev working", self.board, agent_id="main-agent")
        
        # Try direct move to done
        with self.assertRaises(PermissionError) as ctx:
            kb.api_move(self.ref, "done", "Self-certifying to done", self.board, agent_id="main-agent")
        self.assertIn("Direct transition to 'done' is forbidden via kanban_move", str(ctx.exception))

    def test_main_agent_in_work_mode_cannot_call_kanban_qa(self):
        """Main agent in work mode without valid qa_passkey OTP is physically blocked from kanban_qa."""
        captured = []
        orig_send = mcp_server.send_response
        mcp_server.send_response = lambda r: captured.append(r)
        try:
            mcp_server.handle_tool_call(
                req_id=1,
                name="kanban_qa",
                args={"action": "start", "ref": self.ref},
                board=self.board,
                mode="work"
            )
            mcp_server.handle_tool_call(
                req_id=2,
                name="kanban_qa",
                args={"action": "start", "ref": self.ref, "qa_passkey": "kbqa_forged_guess"},
                board=self.board,
                mode="work"
            )
        finally:
            mcp_server.send_response = orig_send
        self.assertTrue(captured[0]["result"].get("isError"))
        self.assertIn("FORBIDDEN: missing 'qa_passkey'", captured[0]["result"]["content"][0]["text"])
        self.assertTrue(captured[1]["result"].get("isError"))
        self.assertIn("FORBIDDEN: invalid or already-rotated 'qa_passkey'", captured[1]["result"]["content"][0]["text"])

    def test_pre_tool_guard_blocks_main_agent_and_other_subagents(self):
        """PreToolUse hook blocks main agent and other subagents (e.g. Explore, Reviewer)."""
        # Main agent
        ok_main, reason_main = guard.evaluate_claude({
            "tool_name": "mcp__kanban-qa__kanban_qa",
            "tool_input": {"action": "approve"},
        })
        self.assertFalse(ok_main)
        self.assertIn("restricted exclusively to the 'kb-qa' subagent", reason_main)
        self.assertIn("caller='main-agent'", reason_main)

        # Other subagent (e.g. Researcher, Explorer, Reviewer)
        for other_subagent in ["Explore", "Researcher", "General-Worker", "reviewer"]:
            ok_sub, reason_sub = guard.evaluate_claude({
                "tool_name": "mcp__kanban-qa__kanban_qa",
                "agent_type": other_subagent,
                "tool_input": {"action": "approve"},
            })
            self.assertFalse(ok_sub, f"Expected {other_subagent} to be blocked")
            self.assertIn(f"caller='{other_subagent}'", reason_sub)

        # Antigravity guard blocks reading .qa_passkey and kb-qa.md so main agent cannot steal OTP
        ok_agy, reason_agy = guard.evaluate_antigravity({
            "toolCall": {
                "name": "read_file",
                "args": {"Path": "C:/Users/dev/.gemini/config/agents/kb-qa.md"}
            }
        })
        self.assertFalse(ok_agy)
        self.assertIn("BLOCKED", reason_agy)

    def test_pre_tool_guard_allows_kb_qa_subagent(self):
        """PreToolUse hook explicitly ALLOWS the dedicated kb-qa subagent."""
        ok_qa, reason_qa = guard.evaluate_claude({
            "tool_name": "mcp__kanban-qa__kanban_qa",
            "agent_type": "kb-qa",
            "tool_input": {"action": "approve"},
        })
        self.assertTrue(ok_qa)
        self.assertEqual(reason_qa, "")

    def test_kb_qa_subagent_complete_successful_approval(self):
        """The dedicated kb-qa subagent legitimately certifies verify -> done."""
        # 1. Author works on ticket in-progress
        kb.api_move(self.ref, "in-progress", "Dev claimed", self.board, agent_id="dev")
        kb.api_checkpoint(
            self.ref,
            board=self.board,
            checked_nodes=["M1", "M2"],
            node_proofs={
                "M1": "Implemented logic in logic.py",
                "M2": "Verified unit test passes",
            },
            files=["logic.py"],
        )

        # 2. Author creates real file change in workspace
        code_file = self.workspace / "logic.py"
        code_file.write_text("VALUE = 42\n", encoding="utf-8")

        # 3. Author moves to verify (passes Gate 2 because git detects logic.py)
        res_verify = kb.api_move(self.ref, "verify", "Done, handover to kb-qa", self.board, workspace=str(self.workspace))
        self.assertEqual(res_verify["to"], "verify")

        # 4. kb-qa launches with --mode qa and executes kanban_qa(action='start')
        captured_start = []
        orig_send = mcp_server.send_response
        mcp_server.send_response = lambda r: captured_start.append(r)
        try:
            mcp_server.handle_tool_call(
                req_id=10,
                name="kanban_qa",
                args={"action": "start", "ref": self.ref, "qa_passkey": self.passkey},
                board=self.board,
                mode="qa"
            )
        finally:
            mcp_server.send_response = orig_send

        self.assertFalse(captured_start[0]["result"].get("isError"))
        start_payload = json.loads(captured_start[0]["result"]["content"][0]["text"])
        qa_nonce = start_payload["qa_nonce"]
        self.assertTrue(bool(qa_nonce))

        # 5. kb-qa writes 4-tier evidence report
        ev_file = self.workspace / "evidence.md"
        ev_file.write_text(f"""# QA Evidence Report: {self.ref}
Auditor: kb-qa
Nonce: {qa_nonce}

## 0. Process & Checkpoint Execution Audit
- [START] -> M1 -> M2
- Cited Mandatory Checkpoints: M2
- Real proofs verified in Execution Log.

## 1. Minimal Diff Review
- Files modified: logic.py
- Diff is strictly minimal and clean.

## 2. Living Architecture & Charter Audit
- Charter and spec inspected; no public API changes.

## 3. Positive Test Results
- python -c 'import logic' -> PASSED

## 4. Negative Discriminator Verification
- Boundary conditions and invalid inputs rejected properly.

## 5. Certification
Verdict: PASS
""", encoding="utf-8")

        # 6. kb-qa calls kanban_qa(action='approve') in mode 'qa'
        captured_approve = []
        mcp_server.send_response = lambda r: captured_approve.append(r)
        try:
            mcp_server.handle_tool_call(
                req_id=11,
                name="kanban_qa",
                args={
                    "action": "approve",
                    "ref": self.ref,
                    "qa_passkey": self.passkey,
                    "qa_nonce": qa_nonce,
                    "evidence_path": str(ev_file),
                    "note": "Certified by kb-qa 4-tier audit",
                    "workspace": str(self.workspace),
                },
                board=self.board,
                mode="qa"
            )
        finally:
            mcp_server.send_response = orig_send

        self.assertFalse(captured_approve[0]["result"].get("isError"), f"Approval failed: {captured_approve}")
        app_text = captured_approve[0]["result"]["content"][0]["text"]
        self.assertIn("CERTIFIED BY QA", app_text)

        # 6b. Verify static-per-install passkey remains valid for subsequent kb-qa runs in the same session
        self.assertTrue(kb_qa_otp.verify_passkey(self.passkey)[0])
        self.assertEqual(kb_qa_otp.load_passkey(), self.passkey)
        self.assertIn(f"QA_PASSKEY: {self.passkey}", self.agent_md.read_text(encoding="utf-8"))

        # 7. Verify ticket status is now 'done'
        ticket_path = kb.resolve_ref(self.ref, self.board)
        meta, _ = kb.parse_frontmatter(ticket_path.read_text(encoding="utf-8"))
        self.assertEqual(meta["status"], "done")
        self.assertTrue(bool(meta.get("qa_signature")))
        self.assertTrue(bool(meta.get("qa_evidence_sha256")))

        # 8. Cryptographic HMAC signature passes verification
        ok_sig, sig_msg = kb.verify_qa_signature(self.ref, meta, self.secret)
        self.assertTrue(ok_sig, f"HMAC signature failed: {sig_msg}")

        # 9. Verify Ephemeral Nonce is BURNED and cannot be reused
        captured_replay = []
        mcp_server.send_response = lambda r: captured_replay.append(r)
        try:
            mcp_server.handle_tool_call(
                req_id=12,
                name="kanban_qa",
                args={
                    "action": "approve",
                    "ref": self.ref,
                    "qa_passkey": self.passkey,
                    "qa_nonce": qa_nonce,
                    "evidence_path": str(ev_file),
                    "note": "Replay attack",
                },
                board=self.board,
                mode="qa"
            )
        finally:
            mcp_server.send_response = orig_send
        self.assertTrue(captured_replay[0]["result"].get("isError"))
        self.assertIn("Invalid or expired qa_nonce", captured_replay[0]["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
