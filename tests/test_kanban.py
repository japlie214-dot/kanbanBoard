"""Automated test suite for kanban-board plugin with 7-Tool Harmonized Arsenal & Anti-Laziness Gates."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

# Add project root
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))
import kb
import mcp_server


class TestKanbanCore(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="kanban_test_"))
        self.board = self.test_dir / "board"
        self.board.mkdir(parents=True, exist_ok=True)
        os.environ["KANBAN_WORKSPACE_ROOT"] = str(self.test_dir)
        kb.api_init("demo", "feature", self.board)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_lifecycle_and_anti_laziness_gates(self):
        # 1. Create ticket
        res = kb.api_create("demo/feature/T001", "Add OAuth Authentication", self.board)
        self.assertEqual(res["status"], "backlog")
        ticket_path = Path(res["path"])
        self.assertTrue(ticket_path.exists())

        # 2. Gate 1: Try moving to in-progress with unfilled sections -> fails
        with self.assertRaises(ValueError) as ctx:
            kb.api_move("demo/feature/T001", "in-progress", "", self.board)
        self.assertIn("required sections missing or empty", str(ctx.exception))

        # 3. Try moving to in-progress with acceptance already checked -> fails (Premature completion)
        premature_content = (
            "---\n"
            "title: Add OAuth Authentication\n"
            "status: backlog\n"
            "since: 2026-11-20\n"
            "note: null\n"
            "depends: []\n"
            "files: []\n"
            "---\n\n"
            "## Outcome\n"
            "Users can log in with Google OAuth and receive a valid JWT session token.\n\n"
            "## Scope\n"
            "- Files modified: src/auth.py, tests/test_auth.py.\n"
            "- Out of scope: User database migrations or billing code.\n\n"
            "## Plan (Todo Tree)\n"
            "- [x] 1. Implementation\n"
            "  - [x] 1A. [ACCEPTANCE] Already done\n\n"
            "## Prove\n"
            "pytest tests/test_auth.py\n"
        )
        ticket_path.write_text(premature_content, encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            kb.api_move("demo/feature/T001", "in-progress", "Starting", self.board)
        self.assertIn("already checked", str(ctx.exception))

        # 4. Fill with valid unchecked plan
        valid_inprogress_content = (
            "---\n"
            "title: Add OAuth Authentication\n"
            "status: backlog\n"
            "since: 2026-11-20\n"
            "note: null\n"
            "depends: []\n"
            "files: []\n"
            "---\n\n"
            "## Outcome\n"
            "Users can log in with Google OAuth and receive a valid JWT session token.\n\n"
            "## Scope\n"
            "- Files modified: src/auth.py, tests/test_auth.py.\n"
            "- Out of scope: User database migrations or billing code.\n\n"
            "## Plan (Todo Tree)\n"
            "- [ ] 1. Core OAuth flow\n"
            "  - [ ] 1A. Google provider [CHOSEN]\n"
            "    - [ ] 2A. Token endpoint\n"
            "    - [ ] 3A. [ACCEPTANCE] Valid Google OAuth token returns HTTP 200 with JWT\n"
            "  - [ ] 1B. GitHub fallback [SKIPPED]\n"
            "    - [ ] 2B. [ACCEPTANCE] GitHub auth works\n\n"
            "## Prove\n"
            "pytest tests/test_auth.py\n"
        )
        ticket_path.write_text(valid_inprogress_content, encoding="utf-8")

        # 5. Move to in-progress -> succeeds and atomically claims ticket
        res = kb.api_move("demo/feature/T001", "in-progress", "Starting auth work", self.board, agent_id="agent-alpha")
        self.assertEqual(res["to"], "in-progress")
        self.assertIsNotNone(res.get("owner"))
        self.assertEqual(res["owner"]["agent"], "agent-alpha")

        # 6. Another agent attempts to claim without force -> blocked
        with self.assertRaises(PermissionError) as ctx:
            kb.api_claim("demo/feature/T001", agent_id="agent-beta", board=self.board)
        self.assertIn("held by agent-alpha", str(ctx.exception))

        # 7. Checkpoint: update Todo Tree checks and files
        kb.api_checkpoint(
            "demo/feature/T001",
            checked_nodes=["1. Core OAuth flow", "1A. Google provider [CHOSEN]", "2A. Token endpoint", "3A. [ACCEPTANCE] Valid Google OAuth token returns HTTP 200 with JWT"],
            files=["src/auth.py", "tests/test_auth.py"],
            notes="Implemented Google OAuth handler and tests.",
            board=self.board
        )

        # 8. Move to verify -> succeeds and validates unbroken DAG path
        res = kb.api_move("demo/feature/T001", "verify", "Ready for QA review", self.board)
        self.assertEqual(res["to"], "verify")
        self.assertTrue(res.get("qa_nonce_generated"))
        self.assertEqual(res["owner"]["agent"], "kb-qa")

        # 9. Anti-cheat check: Primary agent calls api_move with done -> strictly rejected
        with self.assertRaises(PermissionError) as ctx:
            kb.api_move("demo/feature/T001", "done", "Self-approving", self.board, caller_is_qa=False)
        self.assertIn("Direct transition to 'done' is forbidden", str(ctx.exception))

        # 10. QA starts session and retrieves nonce
        qa_data = kb.api_qa_start("demo/feature/T001", self.board)
        self.assertIn("qa_nonce", qa_data)
        nonce = qa_data["qa_nonce"]

        # 11. QA approve with insubstantial evidence -> rejected
        ev_dir = self.test_dir / "evidence" / "demo" / "feature"
        ev_dir.mkdir(parents=True, exist_ok=True)
        ev_file = ev_dir / "T001-qa.md"
        ev_file.write_text("looks good", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            kb.api_qa_approve("demo/feature/T001", nonce, str(ev_file), "Approved", self.board)
        self.assertIn("fails audit", str(ctx.exception))

        # 12. QA approve with substantive evidence -> succeeds to done
        substantive_ev = (
            "# QA Evidence Report: demo/feature/T001\n\n"
            "## 1. Diff & Blast Radius Review\n"
            "Diff inspected: only src/auth.py and tests/test_auth.py modified. Zero unnecessary abstractions.\n\n"
            "## 2. Pass 1 — Positive Tests\n"
            "pytest tests/test_auth.py: 5/5 passed. Expected JWT token returned.\n\n"
            "## 3. Pass 2 — Negative Discriminator Tests\n"
            "Expired token and garbage token return HTTP 401 as expected.\n\n"
            "Verdict: PASS\n"
        )
        ev_file.write_text(substantive_ev, encoding="utf-8")
        res_approve = kb.api_qa_approve("demo/feature/T001", nonce, str(ev_file), "All tests verified", self.board)
        self.assertEqual(res_approve["to"], "done")

    def test_force_takeover(self):
        kb.api_create("demo/feature/T002", "Ticket for takeover", self.board)
        ticket_path = self.board / "demo" / "feature" / "T002.md"
        content = (
            "---\n"
            "title: Ticket for takeover\n"
            "status: backlog\n"
            "since: 2026-11-20\n"
            "note: null\n"
            "depends: []\n"
            "files: []\n"
            "---\n\n"
            "## Outcome\n"
            "Takeover outcome observable description here.\n\n"
            "## Scope\n"
            "- Scope details here.\n\n"
            "## Plan (Todo Tree)\n"
            "- [ ] 1. Task A\n"
            "  - [ ] 2. [ACCEPTANCE] Criteria\n\n"
            "## Prove\n"
            "pytest tests/test_takeover.py\n"
        )
        ticket_path.write_text(content, encoding="utf-8")

        # Claim by agent-1
        kb.api_move("demo/feature/T002", "in-progress", "Agent 1 starting", self.board, agent_id="agent-1")

        # Force claim by agent-2
        res = kb.api_claim(
            "demo/feature/T002",
            agent_id="agent-2",
            force=True,
            reason="Agent 1 hung",
            board=self.board
        )
        self.assertEqual(res["owner"]["agent"], "agent-2")
        self.assertTrue(res["forced"])

    def test_unified_overview_and_attachments(self):
        # Create doc
        kb.api_doc("write", "demo", "feature", "auth-spec", "# OAuth Spec\nToken spec details.", self.board)

        # Overview
        ov = kb.api_overview(self.board)
        self.assertEqual(len(ov["projects"]), 1)
        self.assertEqual(ov["projects"][0]["slug"], "demo")
        self.assertEqual(len(ov["projects"][0]["epics"][0]["docs"]), 1)

        # Attach file
        dummy_file = self.test_dir / "test-run.log"
        dummy_file.write_text("Test output log line 1\nLine 2", encoding="utf-8")

        kb.api_create("demo/feature/T003", "Attachment ticket", self.board)
        att_res = kb.api_attach("demo/feature/T003", str(dummy_file), "Test log output", self.board)
        self.assertEqual(att_res["attached"], "test-run.log")

        # Security check: try attaching .env -> should fail
        env_file = self.test_dir / ".env"
        env_file.write_text("SECRET=12345", encoding="utf-8")
        with self.assertRaises(PermissionError):
            kb.api_attach("demo/feature/T003", str(env_file), "Secret", self.board)

    def test_streamlined_7_mcp_tools(self):
        """Test the 7 streamlined tools via mcp_server.handle_tool_call."""
        responses = []

        def mock_send(req_id, text, is_error=False, extra_result=None):
            responses.append({"id": req_id, "text": text, "is_error": is_error, "extra": extra_result})

        original_send = mcp_server.send_tool_result
        mcp_server.send_tool_result = mock_send

        try:
            # 1. kanban_board (overview, list, lint)
            mcp_server.handle_tool_call(1, "kanban_board", {"view": "overview"}, self.board)
            self.assertIn("projects", responses[-1]["text"])

            mcp_server.handle_tool_call(2, "kanban_board", {"view": "list"}, self.board)
            self.assertFalse(responses[-1]["is_error"])

            mcp_server.handle_tool_call(3, "kanban_board", {"view": "lint"}, self.board)
            self.assertIn("Lint:", responses[-1]["text"])

            # Test lint on empty non-existent board does not fail
            empty_board = self.test_dir / "empty_board"
            mcp_server.handle_tool_call(31, "kanban_board", {"view": "lint"}, empty_board)
            self.assertFalse(responses[-1]["is_error"])
            self.assertIn("empty", responses[-1]["text"].lower())

            # Test explicit board initialization
            mcp_server.handle_tool_call(32, "kanban_board", {"view": "init", "project": "newproj", "epic": "core"}, self.board)
            self.assertIn("Initialized Kanban board", responses[-1]["text"])
            self.assertTrue((self.board / "newproj" / "project.md").exists())

            # Test create with auto ID
            mcp_server.handle_tool_call(33, "kanban_ticket", {"project": "newproj", "epic": "core", "title": "Auto ID Ticket"}, self.board)
            self.assertIn("Created ticket newproj/core/T001", responses[-1]["text"])

            # 2. kanban_ticket (create and show)
            mcp_server.handle_tool_call(4, "kanban_ticket", {"ref": "demo/feature/T010", "title": "New Tool Ticket"}, self.board)
            self.assertIn("Created ticket", responses[-1]["text"])

            mcp_server.handle_tool_call(5, "kanban_ticket", {"ref": "demo/feature/T010"}, self.board)
            self.assertIn("New Tool Ticket", responses[-1]["text"])

            # 3. kanban_doc (write and read)
            mcp_server.handle_tool_call(6, "kanban_doc", {"action": "write", "project": "demo", "name": "arch", "content": "Architecture Spec"}, self.board)
            self.assertIn("Document written", responses[-1]["text"])

            mcp_server.handle_tool_call(7, "kanban_doc", {"action": "read", "project": "demo", "name": "arch"}, self.board)
            self.assertIn("Architecture Spec", responses[-1]["text"])

            # 4. kanban_update (checkpoint + attach)
            log_file = self.test_dir / "sample.log"
            log_file.write_text("sample log", encoding="utf-8")
            mcp_server.handle_tool_call(8, "kanban_update", {"ref": "demo/feature/T010", "notes": "Work in progress", "attach_file": str(log_file)}, self.board)
            self.assertIn("Attached sample.log", responses[-1]["text"])
            self.assertIn("Checkpoint saved", responses[-1]["text"])

            # 5. kanban_move
            # Trying to move to in-progress with template fails Gate 1
            mcp_server.handle_tool_call(9, "kanban_move", {"ref": "demo/feature/T010", "status": "in-progress"}, self.board)
            self.assertTrue(responses[-1]["is_error"])

            # 6. kanban_view
            mcp_server.handle_tool_call(10, "kanban_view", {"open_browser": False}, self.board)
            self.assertIn("Overview", responses[-1]["text"])

            # 7. kanban_qa
            mcp_server.handle_tool_call(11, "kanban_qa", {"action": "start", "ref": "demo/feature/T010"}, self.board)
            # Fails because ticket is in backlog, not verify -> is_error
            self.assertTrue(responses[-1]["is_error"])

        finally:
            mcp_server.send_tool_result = original_send


if __name__ == "__main__":
    unittest.main()
