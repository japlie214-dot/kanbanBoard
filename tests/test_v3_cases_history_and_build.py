"""tests/test_v3_cases_history_and_build.py – Positive & Negative (Pluto) tests for KanbanBoard v3.0."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import kb_cases
import kb_crud
import kb_history
import kb_repo_id
import scripts.migrate_in_progress_to_build as migrator


class TestCasesLifecycle(unittest.TestCase):
    def _mk_ticket(self, board: Path, proj: str, epic: str, tid: str, status: str = "build") -> Path:
        p = board / proj / epic / f"{tid}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"---\ntitle: {tid} title\nstatus: {status}\n---\n\n## Outcome\nTest\n", encoding="utf-8")
        return p

    def test_case_cross_project_links_attachments_and_deleted_tombstone(self):
        with tempfile.TemporaryDirectory() as td:
            board = Path(td) / "board"
            self._mk_ticket(board, "alpha", "core", "T001", status="verify")
            self._mk_ticket(board, "beta", "ui", "T002", status="backlog")
            att = Path(td) / "proof.json"
            att.write_text('{"ok": true}\n', encoding="utf-8")

            t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
            created = kb_cases.api_case_create(
                title="Cross-repo QA proof",
                tickets=["alpha/core/T001", "beta/ui/T002"],
                body="Unit + integration passed.",
                board=board,
                kind="qa",
                author="kb-qa",
                attachments=[str(att)],
                now=t0,
            )
            self.assertEqual(created["id"], "C001")
            self.assertEqual(created["projects"], ["alpha", "beta"])
            self.assertEqual(created["epics"], ["alpha/core", "beta/ui"])
            self.assertEqual(len(created["attachments"]), 1)

            # Reply
            rep = kb_cases.api_case_reply("C001", "worker", "Fixed edge case.", board, now=t0 + timedelta(hours=1))
            self.assertTrue(rep["ok"])

            # Retire & purge beta/ui/T002 after 121 days -> Case must show [DELETED] tombstone!
            kb_crud.api_retire("beta/ui/T002", "Obsolete UI tweak", board, now=t0)
            kb_crud.purge_expired_retired(board, force=True, now=t0 + timedelta(days=121))

            shown = kb_cases.api_case_show("C001", board)
            self.assertEqual(shown["deleted_ticket_count"], 1)
            t2 = [x for x in shown["linked_tickets"] if x["ref"] == "beta/ui/T002"][0]
            self.assertTrue(t2["deleted"])
            self.assertIn("[DELETED: beta/ui/T002", t2["tombstone"])

    def test_case_negative_rejects_zero_or_over_100_tickets(self):
        with tempfile.TemporaryDirectory() as td:
            board = Path(td) / "board"
            with self.assertRaises(ValueError):
                kb_cases.api_case_create("No tickets", [], "body", board)
            with self.assertRaises(ValueError):
                kb_cases.api_case_create("Too many", [f"p/e/T{i}" for i in range(101)], "body", board)

    def test_case_auto_archive_after_180_days_when_all_done_or_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            board = Path(td) / "board"
            self._mk_ticket(board, "alpha", "core", "T001", status="done")
            t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
            kb_cases.api_case_create("Old QA case", ["alpha/core/T001"], "PASS", board, now=t0)
            res = kb_cases.archive_stale_cases(board, force=True, now=t0 + timedelta(days=185))
            self.assertEqual(res["archived_count"], 1)
            self.assertEqual(res["archived"], ["C001"])


class TestHistoryAndRepoIdAndBuildMigration(unittest.TestCase):
    def test_history_deduplicates_unchanged_body_snapshots(self):
        with tempfile.TemporaryDirectory() as td:
            board = Path(td)
            e1 = kb_history.record_transition("p/e/T1", "backlog", "build", "agent", board, body="## Outcome\nV1")
            e2 = kb_history.record_transition("p/e/T1", "build", "verify", "agent", board, body="## Outcome\nV1")
            self.assertIn("body_snapshot", e1)
            self.assertNotIn("body_snapshot", e2)  # Deduplicated on disk!

            hist = kb_history.read_history("p/e/T1", board)
            self.assertEqual(len(hist), 2)
            self.assertEqual(hist[1]["body_snapshot"], "## Outcome\nV1")  # Hydrated on read!

    def test_repo_identity_matches_project_md_even_after_folder_rename(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "messy_folder_name"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=str(repo), check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "a"], cwd=str(repo), check=True, capture_output=True)
            (repo / "README.md").write_text("hi\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), check=True, capture_output=True)

            ident = kb_repo_id.resolve_repo_identity(repo)
            self.assertTrue(ident["root_commit"])

            board = Path(td) / "board"
            pmd = board / "myproj" / "project.md"
            pmd.parent.mkdir(parents=True)
            pmd.write_text(f"---\nrepo_root_commit: {ident['root_commit']}\n---\n# MyProj\n", encoding="utf-8")
            self.assertEqual(kb_repo_id.match_project_by_repo(repo, board), "myproj")

    def test_migrate_in_progress_to_build_preserves_done(self):
        with tempfile.TemporaryDirectory() as td:
            board = Path(td) / "board"
            p1 = board / "a" / "b" / "T001.md"
            p2 = board / "a" / "b" / "T002.md"
            p1.parent.mkdir(parents=True)
            p1.write_text("---\ntitle: Active\nstatus: in-progress\n---\nBody\n", encoding="utf-8")
            p2.write_text("---\ntitle: Done\nstatus: done\nqa_signature: abc\n---\nBody\n", encoding="utf-8")

            changed = migrator.migrate_board(board, apply=True)
            self.assertEqual(changed, ["a/b/T001.md"])
            self.assertIn("status: build", p1.read_text(encoding="utf-8"))
            self.assertIn("status: done", p2.read_text(encoding="utf-8"))

    def test_mcp_kanban_case_and_qa_reject_unchecks_mandatory_and_logs_history(self):
        import json
        import kb
        import mcp_server

        with tempfile.TemporaryDirectory() as td:
            board = Path(td) / "board"
            kb.api_init("demo", "core", board)
            created = kb.api_create("demo/core/T001", "v3 reject uncheck test", board)
            ref = created["ref"]
            tpath = Path(created["path"])
            kb.api_ticket_edit(
                ref,
                board=board,
                outcome="Reject uncheck works cleanly across lifecycle transitions",
                scope="Allowed files: kb.py, mcp_server.py",
                plan="- [ ] A1 [START] Build\n- [ ] A2 [after:A1] [ACCEPTANCE:MANDATORY] Verified\n",
                prove="python -c 'print(1)'",
            )
            # "in-progress" alias -> canonical "build"
            mv1 = kb.api_move(ref, "in-progress", "Start build", board, agent_id="dev")
            self.assertEqual(mv1["to"], "build")

            kb.api_checkpoint(
                ref,
                checked_nodes=["A1", "A2"],
                node_proofs={"A1": "Implemented build logic cleanly", "A2": "Verified unit tests pass"},
                files=["kb.py"],
                board=board,
            )
            kb.api_move(ref, "verify", "Ready for QA", board, workspace=td)
            qa = kb.api_qa_start(ref, board)
            rej = kb.api_qa_reject(ref, qa["qa_nonce"], "Missing edge case check", board)
            self.assertEqual(rej["to"], "build")
            # Mandatory acceptance leaf must be unchecked after QA reject!
            self.assertIn("- [ ] A2", tpath.read_text(encoding="utf-8"))

            # Transition history recorded & deduplicated
            hist = kb_history.read_history(ref, board)
            self.assertEqual([h["to"] for h in hist], ["build", "verify", "build"])

            # MCP kanban_case roundtrip
            captured = []
            orig_send = mcp_server.send_tool_result
            mcp_server.send_tool_result = lambda req_id, text, is_error=False, extra_result=None: captured.append((text, is_error))
            try:
                mcp_server.handle_tool_call(
                    1,
                    "kanban_case",
                    {"action": "create", "title": "QA reject note", "tickets": [ref], "body": "Reject proof", "kind": "qa"},
                    board,
                )
                self.assertFalse(captured[-1][1], captured[-1][0])
                cid = json.loads(captured[-1][0])["id"]
                mcp_server.handle_tool_call(2, "kanban_case", {"action": "list", "ticket": ref}, board)
                self.assertEqual(json.loads(captured[-1][0])["pagination"]["total_items"], 1)
                mcp_server.handle_tool_call(3, "kanban_case", {"action": "show", "case_id": cid}, board)
                self.assertEqual(json.loads(captured[-1][0])["id"], cid)
            finally:
                mcp_server.send_tool_result = orig_send

    def test_lint_and_loaders_ignore_cases_and_history_system_dirs(self):
        import kb

        with tempfile.TemporaryDirectory() as td:
            board = Path(td) / "board"
            kb.api_init("demo", "core", board)
            created = kb.api_create("demo/core/T001", "Lint system dir check", board)
            ref = created["ref"]
            att = Path(td) / "log.txt"
            att.write_text("ok\n", encoding="utf-8")
            kb_cases.api_case_create(
                title="Case with attachment",
                tickets=[ref],
                body="Proof attached.",
                board=board,
                kind="qa",
                author="kb-qa",
                attachments=[str(att)],
            )
            kb_history.record_transition(ref, "backlog", "build", "dev", board, body="## Outcome\nTest")

            lint_res = kb.api_lint(board)
            self.assertEqual(lint_res["errors"], [], f"Unexpected lint errors: {lint_res['errors']}")

            ov = kb.api_overview(board)
            self.assertEqual([p["slug"] for p in ov["projects"]], ["demo"])

            listed = kb.api_list(board)
            self.assertEqual([t["ref"] for t in listed], [ref])

            resolved = kb.resolve_ref("core/T001", board)
            self.assertEqual(resolved.name, "T001.md")

            payload = kb.api_board_payload(board)
            self.assertEqual([p["slug"] for p in payload["board"]["projects"]], ["demo"])


if __name__ == "__main__":
    unittest.main()
