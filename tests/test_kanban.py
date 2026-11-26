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
import viewer
import urllib.request


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
            "- [ ] A1 [START] [lane:A] Core OAuth flow\n"
            "- [ ] A2 [lane:A] [after:A1] Google provider [CHOSEN]\n"
            "- [ ] A3 [lane:A] [after:A2] Token endpoint\n"
            "- [ ] A4 [lane:A] [after:A3] [ACCEPTANCE:MANDATORY] Valid Google OAuth token returns HTTP 200 with JWT\n\n"
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
            checked_nodes=["A1", "A2", "A3", "A4"],
            node_proofs={
                "A1": "Core OAuth flow design verified",
                "A2": "Google provider configured",
                "A3": "Token endpoint tested",
                "A4": "Valid Google OAuth token returns HTTP 200 with JWT verified",
            },
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
            "## 0. Process & Checkpoint Audit\n"
            "Verified A4 from START with Execution Log.\n\n"
            "## 1. Diff & Blast Radius Review\n"
            "Diff inspected: only src/auth.py and tests/test_auth.py modified. Zero unnecessary abstractions.\n\n"
            "## Living Architecture\n"
            "Living architecture updated with OAuth specs.\n\n"
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
            "- [ ] A1 [START] [lane:A] Task A\n"
            "- [ ] A2 [lane:A] [after:A1] [ACCEPTANCE:MANDATORY] Criteria\n\n"
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

    def test_abcde_dag_parallel_ifelse_mandatory_optional_and_process_qa(self):
        """Verify the exact A/B/C/D/E workflow topology and process verification."""
        board = self.board
        kb.api_init("demo", "dag", board)
        created = kb.api_create("demo/dag/T010", "ABCDE DAG Workflow", board)
        ref = created["ref"]

        abcde_plan = "\n".join([
            "- [ ] A1 [START] [lane:A] Initialize & evaluate fork1",
            "- [ ] A2 [lane:A] [after:A1] Happy path step 2",
            "- [ ] B1 [lane:B] [after:A1] [when:if(cond1):fork1] Branch B step 1",
            "- [ ] B2 [lane:B] [after:B1] Branch B step 2",
            "- [ ] B3 [lane:B] [after:B2] Branch B step 3",
            "- [ ] C1 [lane:C] [after:A1] [when:else(cond1):fork1] Branch C step 1",
            "- [ ] C2 [lane:C] [after:C1] [ACCEPTANCE:MANDATORY] Early exit C acceptance",
            "- [ ] A3 [lane:A] [after:A2,B3?] Merge A2 and B3",
            "- [ ] A4 [lane:A] [after:A3] Fan-out decision checkpoint",
            "- [ ] B4 [lane:B] [after:A4] [when:if(cond2):fork2] Branch B phase 2",
            "- [ ] B5 [lane:B] [after:B4] Branch B phase 2 end",
            "- [ ] C4 [lane:C] [after:A4] [when:else(cond2):fork2] Branch C phase 2",
            "- [ ] C5 [lane:C] [after:C4] Branch C phase 2 end",
            "- [ ] A5 [lane:A] [after:A4,B5|C5] Converge after A4 and B5|C5",
            "- [ ] A6 [lane:A] [after:A5] [ACCEPTANCE:MANDATORY] Happy path acceptance",
            "- [ ] D1 [lane:D] [after:A1] [parallel] Parallel lane D step 1",
            "- [ ] D2 [lane:D] [after:D1] Parallel lane D step 2",
            "- [ ] D3 [lane:D] [after:D2] Parallel lane D step 3",
            "- [ ] D4 [lane:D] [after:D3] [ACCEPTANCE:MANDATORY] Parallel D acceptance",
            "- [ ] E1 [lane:E] [after:A4] [optional] Optional branch E step 1",
            "- [ ] E2 [lane:E] [after:E1] [ACCEPTANCE:OPTIONAL] Optional E acceptance",
        ])

        kb.api_ticket_edit(
            ref,
            board=board,
            outcome="DAG workflow with parallel D, if/else B&C, mandatory A6&D4, optional E2.",
            scope="- Allowed: `kb.py`, `mcp_server.py`\n- Out of scope: external deps",
            plan=abcde_plan,
            prove="```bash\npython3 -m unittest tests/test_kanban.py\n```",
        )
        kb.api_move(ref, "in-progress", "Starting ABCDE DAG", board, agent_id="agent-a")

        # Dependency order enforcement: cannot check A2 before A1
        with self.assertRaises(ValueError):
            kb.api_checkpoint(ref, checked_nodes=["A2"], node_proofs={"A2": "ran step 2"}, board=board)

        # Process proof enforcement: cannot check A1 without proof
        with self.assertRaises(ValueError):
            kb.api_checkpoint(ref, checked_nodes=["A1"], board=board)

        # Complete A1 -> A2, B1, C1, D1 become ready in parallel!
        cp = kb.api_checkpoint(ref, checked_nodes=["A1"], node_proofs={"A1": "init ok"}, board=board)
        self.assertIn("D1", cp["ready_nodes"])
        self.assertIn("A2", cp["ready_nodes"])

        # Skip else branch C1/C2, run A2 + B1..B3 -> A3 -> A4, skip C4/C5, run B4..B5 -> A5 -> A6
        kb.api_checkpoint(
            ref,
            checked_nodes=["A2", "B1", "B2", "B3", "A3", "A4", "B4", "B5", "A5", "A6"],
            skip_nodes=["C1", "C2", "C4", "C5", "E1", "E2"],
            skip_reason="cond1=true, cond2=true, optional E skipped",
            node_proofs={nid: f"executed {nid} verified" for nid in ["A2", "B1", "B2", "B3", "A3", "A4", "B4", "B5", "A5", "A6"]},
            files=["kb.py"],
            board=board,
        )

        # Gate 3 MUST STILL FAIL because mandatory parallel acceptance D4 is not done!
        with self.assertRaises(ValueError) as ctx:
            kb.api_move(ref, "verify", "Only A done", board)
        self.assertIn("D4", str(ctx.exception))

        # Complete parallel lane D1 -> D4 (E remains skipped and optional!)
        kb.api_checkpoint(
            ref,
            checked_nodes=["D1", "D2", "D3", "D4"],
            node_proofs={nid: f"parallel {nid} verified" for nid in ["D1", "D2", "D3", "D4"]},
            board=board,
        )

        # Now Gate 3 passes even though optional E2 was skipped!
        res = kb.api_move(ref, "verify", "All mandatory acceptances A6 & D4 done", board)
        self.assertEqual(res["to"], "verify")

        # Gate 5 QA Process Audit: reject if evidence omits Process & Checkpoint Audit or D4
        qa = kb.api_qa_start(ref, board)
        bad_ev = self.test_dir / "bad-qa.md"
        bad_ev.write_text("# QA\n## Diff\nOK\n## Positive Tests\nPASS\n## Negative Discriminator Tests\nPASS\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            kb.api_qa_approve(ref, qa["qa_nonce"], str(bad_ev), "incomplete", board)

        good_ev = self.test_dir / "good-qa.md"
        good_ev.write_text(
            "# QA Evidence Report\nVerdict: PASS\n"
            "## 0. Process & Checkpoint Audit\nVerified A6 and D4 from START with Execution Log.\n"
            "## 1. Diff\nMinimal diff verified.\n## Living Architecture\nLiving Architecture updated.\n"
            "## 2. Positive Tests\nPASS\n"
            "## 3. Negative Discriminator Tests\nPASS\n",
            encoding="utf-8",
        )
        approved = kb.api_qa_approve(ref, qa["qa_nonce"], str(good_ev), "Certified", board)
        self.assertEqual(approved["to"], "done")

    def test_mcp_ux_fixes_doc_default_and_qa_reject(self):
        """Verify kanban_doc optional name, action='list', and kanban_qa action='reject'."""
        board = self.board
        kb.api_init("ux", "core", board)
        # Default name -> project.md
        w = kb.api_doc("write", "ux", None, None, "# Project Charter", board)
        self.assertTrue(w["path"].endswith("project.md"))
        r = kb.api_doc("read", "ux", None, None, "", board)
        self.assertIn("Project Charter", r["content"])
        lst = kb.api_doc("list", "ux", None, None, "", board)
        self.assertIn("project", lst["docs"])

        # Default name with epic -> epic.md
        we = kb.api_doc("write", "ux", "core", None, "# Epic Spec", board)
        self.assertTrue(we["path"].endswith("epic.md"))
        re = kb.api_doc("read", "ux", "core", None, "", board)
        self.assertIn("Epic Spec", re["content"])

        # Ticket edit + QA reject flow
        created = kb.api_create("ux/core/T001", "QA reject test", board)
        ref = created["ref"]
        plan = (
            "- [ ] A1 [START] [lane:A] Step 1\n"
            "- [ ] A2 [lane:A] [after:A1] [ACCEPTANCE:MANDATORY] Final step\n"
        )
        kb.api_ticket_edit(
            ref,
            board=board,
            outcome="Observable test outcome.",
            scope="- src/ux.py",
            plan=plan,
            prove="```bash\npytest\n```",
        )
        kb.api_move(ref, "in-progress", "Starting", board, agent_id="agent-1")
        kb.api_checkpoint(ref, checked_nodes=["A1", "A2"], node_proofs={"A1": "done A1", "A2": "done A2"}, files=["src/ux.py"], board=board)
        kb.api_move(ref, "verify", "Ready for QA", board)
        qa = kb.api_qa_start(ref, board)
        rej = kb.api_qa_reject(ref, qa["qa_nonce"], "Found a bug in step A2", board)
        self.assertEqual(rej["to"], "in-progress")
        self.assertIn("Found a bug in step A2", rej["note"])

    def test_lenient_execution_log_scaffolding_and_fuzzy_qa(self):
        """Verify lenient execution log parsing, DAG scaffolding templates, and fuzzy QA header matching."""
        # 1. Lenient execution log parsing
        sample_log = (
            "## Execution Log\n"
            "- [2026-11-23 08:00 UTC] [DONE] A1 | proof: canonical evidence A1\n"
            "- Node A2: human formatted evidence A2\n"
            "- [B1]: evidence for node B1\n"
            "- [x] B2: evidence for node B2\n"
            "- Node C1 (SKIP): skipped branch C1\n"
        )
        parsed = kb.parse_execution_log(sample_log)
        self.assertIn("A1", parsed)
        self.assertIn("A2", parsed)
        self.assertIn("B1", parsed)
        self.assertIn("B2", parsed)
        self.assertIn("C1", parsed)
        self.assertEqual(parsed["A2"][0]["kind"], "DONE")
        self.assertEqual(parsed["C1"][0]["kind"], "SKIP")
        self.assertEqual(parsed["A2"][0]["detail"], "human formatted evidence A2")

        # 2. Scaffolding templates
        for pat in ["agile", "feature", "spike", "refactor"]:
            scaffold = kb.api_scaffold_dag(pat)
            self.assertIn("[START]", scaffold)
            self.assertIn("[ACCEPTANCE", scaffold)
            nodes, err = kb.parse_todo_tree(scaffold)
            self.assertEqual(err, "")
            self.assertIsNotNone(nodes)
            valid, msg = kb.validate_todo_tree(nodes, for_inprogress=True, body=scaffold)
            self.assertTrue(valid, f"Pattern '{pat}' failed validation: {msg}")

        # 3. Create ticket with default agile scaffolding
        t = kb.api_create("ux/core/T002", "Scaffolded ticket test", self.board, pattern="agile")
        self.assertEqual(t["status"], "backlog")
        show = kb.api_show("ux/core/T002", self.board)
        self.assertIn("## Plan (Todo Tree)", show["body"])
        self.assertIn("[when:if(fast_path_viable):fork1]", show["body"])

        # 4. Fuzzy QA section matching
        fuzzy_evidence = (
            "# QA Report\n\n"
            "## 0. Process & Checkpoint Execution Audit\n"
            "Node A1 and A2 verified.\n\n"
            "## 1. Minimal Diff Review\n"
            "Clean diff.\n\n"
            "## 2. Living Architecture & Charter Audit\n"
            "Epic documentation checked.\n\n"
            "## 3. Positive Test Results\n"
            "All positive tests pass.\n\n"
            "## 4. Negative Discriminator Verification\n"
            "Direct moves rejected.\n\n"
            "## 5. Certification\n"
            "Final Verdict: PASS\n"
        )
        ev_path = self.test_dir / "fuzzy_qa_evidence.md"
        ev_path.write_text(fuzzy_evidence, encoding="utf-8")

        # Set up a ticket in verify state to approve
        created = kb.api_create("demo/feature/T099", "Fuzzy QA ticket", self.board)
        ref = created["ref"]
        plan = (
            "- [ ] A1 [START] [lane:A] Step 1\n"
            "- [ ] A2 [lane:A] [after:A1] [ACCEPTANCE:MANDATORY] Final step\n"
        )
        kb.api_ticket_edit(
            ref,
            board=self.board,
            outcome="Fuzzy QA outcome.",
            scope="- src/demo.py",
            plan=plan,
            prove="```bash\npytest\n```",
        )
        kb.api_move(ref, "in-progress", "Starting", self.board, agent_id="agent-qa")
        kb.api_checkpoint(ref, checked_nodes=["A1", "A2"], node_proofs={"A1": "done A1", "A2": "done A2"}, files=["src/demo.py"], board=self.board)
        kb.api_move(ref, "verify", "Ready for QA", self.board)
        qa = kb.api_qa_start(ref, self.board)
        app = kb.api_qa_approve(ref, qa["qa_nonce"], str(ev_path), "Fuzzy QA passed", self.board)
        self.assertEqual(app["to"], "done")

    def test_viewer_server_and_ui_payload_masterclass(self):
        """Test the viewer HTTP server, SSE events, payload enrichment, and security invariants."""
        # 1. Test payload enrichment
        payload = kb.api_board_payload(self.board)
        self.assertIn("board", payload)
        self.assertIn("board_dir", payload["board"])
        self.assertEqual(payload["board"]["board_dir"], str(self.board))
        self.assertIn("projects", payload["board"])
        for p in payload["board"]["projects"]:
            for t in p.get("tickets", []):
                self.assertIn("dag_nodes", t)
                self.assertIn("ready_nodes", t)
                self.assertIn("execution_log", t)

        # 2. Test HTML hydration
        html = viewer.get_html_page("test-csrf-token")
        self.assertIn("Kanban Board", html)
        self.assertIn("test-csrf-token", html)
        self.assertIn("/assets/board.css", html)
        self.assertIn("/assets/board.js", html)
        self.assertIn('id="drawer"', html)

        # 3. Test board stamp hashing
        stamp = viewer.board_stamp(self.board)
        self.assertEqual(len(stamp), 64)

        # 4. Start ephemeral viewer server
        server, port = viewer.find_available_server(self.board, preferred_port=8910)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        base_url = f"http://127.0.0.1:{port}"
        try:
            # Positive Test: GET /
            with urllib.request.urlopen(f"{base_url}/") as res:
                self.assertEqual(res.status, 200)
                body = res.read().decode("utf-8")
                self.assertIn("Kanban Board", body)
                self.assertIn("/assets/board.js", body)

            # Positive Test: GET /api/board
            with urllib.request.urlopen(f"{base_url}/api/board") as res:
                self.assertEqual(res.status, 200)
                data = json.loads(res.read().decode("utf-8"))
                self.assertIn("board", data)
                self.assertIn("statuses", data)

            # Positive Test: GET /health
            with urllib.request.urlopen(f"{base_url}/health") as res:
                self.assertEqual(res.status, 200)
                h = json.loads(res.read().decode("utf-8"))
                self.assertTrue(h["ok"])
                self.assertIn("viewer", h.get("mode", ""))

            # Positive Test: HEAD /events
            req = urllib.request.Request(f"{base_url}/events", method="HEAD")
            with urllib.request.urlopen(req) as res:
                self.assertEqual(res.status, 200)
                self.assertIn("text/event-stream", res.headers.get("Content-Type", ""))

            # Negative Test: Unknown route -> 404
            try:
                urllib.request.urlopen(f"{base_url}/invalid-endpoint")
                self.fail("Expected 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)

            # Negative Test: POST to read-only server -> 405
            try:
                post_req = urllib.request.Request(f"{base_url}/api/board", data=b"{}", method="POST")
                urllib.request.urlopen(post_req)
                self.fail("Expected 405")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 405)

            # Positive Test: POST /api/ticket/manual-approve for a ticket in verify
            # Create a ticket in demo/feature and set it to verify
            v_ticket = self.board / "demo" / "feature" / "T099.md"
            v_ticket.write_text(
                "---\nstatus: verify\ntitle: Verify candidate\n---\n\n## Outcome\nO\n## Scope\nS\n## Plan (Todo Tree)\n- [x] A1. [START] [ACCEPTANCE:MANDATORY] Done\n## Prove\npytest\n## Execution Log\n- [2026-11-25 00:00 UTC] [DONE] A1 | proof: ok\n",
                encoding="utf-8"
            )
            approve_payload = json.dumps({
                "ref": "demo/feature/T099",
                "approver": "Boss",
                "reason": "Accepted based on verified device logs."
            }).encode("utf-8")
            post_approve = urllib.request.Request(
                f"{base_url}/api/ticket/manual-approve",
                data=approve_payload,
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{port}",
                    "X-Kanban-CSRF": server.csrf_token,
                },
                method="POST"
            )
            with urllib.request.urlopen(post_approve) as res:
                self.assertEqual(res.status, 200)
                resp_data = json.loads(res.read().decode("utf-8"))
                self.assertTrue(resp_data.get("ok"))
                self.assertEqual(resp_data.get("to"), "done")
                self.assertEqual(resp_data.get("approver"), "Boss")

            # Negative Test: POST /api/ticket/manual-approve on already done ticket -> 400
            try:
                urllib.request.urlopen(post_approve)
                self.fail("Expected 400 for already done ticket")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 400)

        finally:
            server.server_close()
            t.join(timeout=2)

    def test_centralized_board_root_resolution(self):
        """Verify board_root resolution strictly centralizes and never creates board/ in random repos."""
        # 1. KANBAN_BOARD_ROOT env override
        custom_board = self.test_dir / "custom_board"
        custom_board.mkdir()
        try:
            os.environ["KANBAN_BOARD_ROOT"] = str(custom_board)
            self.assertEqual(kb.board_root(), custom_board.resolve())
        finally:
            del os.environ["KANBAN_BOARD_ROOT"]

        # 2. KANBAN_WORKSPACE_ROOT override
        self.assertEqual(kb.board_root(), self.board.resolve())

        # 3. Simulate random git repository without env vars
        old_ws = os.environ.pop("KANBAN_WORKSPACE_ROOT", None)
        try:
            random_repo = self.test_dir / "random_app"
            random_repo.mkdir()
            (random_repo / ".git").mkdir()
            orig_cwd = os.getcwd()
            try:
                os.chdir(str(random_repo))
                resolved = kb.board_root()
                # Must NOT resolve to random_app / board
                self.assertNotEqual(resolved, random_repo / "board")
                self.assertFalse((random_repo / "board").exists())
                # Must resolve to central board (C:/Projects/kanbanBoard/board or ~/.kanban/board)
                expected_primary = Path("C:/Projects/kanbanBoard/board").resolve()
                expected_fallback = (Path.home() / ".kanban" / "board").resolve()
                self.assertIn(resolved, [expected_primary, expected_fallback])
            finally:
                os.chdir(orig_cwd)
        finally:
            if old_ws:
                os.environ["KANBAN_WORKSPACE_ROOT"] = old_ws


    def test_manual_approve_lifecycle_and_security_invariants(self):
        """Test kb.api_manual_approve mechanical gates, logging, and HMAC signatures."""
        kb.api_init("demo", "core", self.board)
        t_path = self.board / "demo" / "core" / "T098.md"
        t_path.write_text(
            "---\nstatus: in-progress\ntitle: Feature in progress\n---\n\n## Outcome\nO\n## Scope\nS\n## Plan (Todo Tree)\n- [x] A1. [START] [ACCEPTANCE:MANDATORY] Done\n## Prove\npytest\n## Execution Log\n- [2026-11-25 00:00 UTC] [DONE] A1 | proof: ok\n",
            encoding="utf-8"
        )
        # 1. Reject if ticket not in 'verify'
        with self.assertRaises(ValueError) as ctx:
            kb.api_manual_approve("demo/core/T098", "Boss", "Valid reason exceeding 10 characters", self.board)
        self.assertIn("Only tickets in 'verify' status can be approved", str(ctx.exception))

        # Set ticket to verify
        t_path.write_text(
            "---\nstatus: verify\ntitle: Feature ready for review\n---\n\n## Outcome\nO\n## Scope\nS\n## Plan (Todo Tree)\n- [x] A1. [START] [ACCEPTANCE:MANDATORY] Done\n## Prove\npytest\n## Execution Log\n- [2026-11-25 00:00 UTC] [DONE] A1 | proof: ok\n",
            encoding="utf-8"
        )

        # 2. Reject if approver too short
        with self.assertRaises(ValueError) as ctx:
            kb.api_manual_approve("demo/core/T098", "A", "Valid reason exceeding 10 characters", self.board)
        self.assertIn("Approver name is required", str(ctx.exception))

        # 3. Reject if reason too short
        with self.assertRaises(ValueError) as ctx:
            kb.api_manual_approve("demo/core/T098", "Boss", "short", self.board)
        self.assertIn("Approval reason is required", str(ctx.exception))

        # 4. Successful manual approval
        res = kb.api_manual_approve(
            "demo/core/T098",
            "Boss",
            "Accepted after reviewing device telemetry and supervisor logs.",
            self.board
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["to"], "done")
        self.assertEqual(res["approver"], "Boss")
        self.assertTrue(res["manual_approval"])

        # Check file content & frontmatter
        meta, body = kb.parse_frontmatter(t_path.read_text(encoding="utf-8"))
        self.assertEqual(meta["status"], "done")
        self.assertTrue(meta["manual_approval"])
        self.assertEqual(meta["approved_by"], "Boss")
        self.assertIn("[MANUAL APPROVAL by Boss]", meta["note"])
        self.assertIn("[MANUAL APPROVAL] by Boss | reason: Accepted after reviewing device telemetry", body)

        # Check HMAC signature verification
        secret = kb.load_qa_secret()
        if secret:
            ok_sig, sig_msg = kb.verify_qa_signature("demo/core/T098", meta, secret)
            self.assertTrue(ok_sig, f"Signature failed: {sig_msg}")

        # Check board lint
        lint_res = kb.api_lint(self.board)
        self.assertEqual(lint_res["errors"], [])


if __name__ == "__main__":
    unittest.main()
