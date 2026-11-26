"""tests/test_v26_crud_and_guard.py – Positive & Negative discriminator tests for KanbanBoard v2.6."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import hooks.guard as guard
import kb_crud


class TestAntigravityAndClaudeGuardIsolation(unittest.TestCase):
    def test_claude_code_explicit_kb_qa_agent_type_allowed(self):
        """Explicit agent_type='kb-qa' via kanban-qa server: allowed."""
        ok_qa, _ = guard.evaluate_claude({
            "tool_name": "mcp__kanban-qa__kanban_qa",
            "tool_input": {"action": "approve"},
            "agent_type": "kb-qa",
        })
        self.assertTrue(ok_qa)

    def test_claude_code_subagent_via_kanban_qa_server_allowed(self):
        """agent_type='subagent' + tool via mcp__kanban-qa__ server: allowed (server name is proof)."""
        ok, _ = guard.evaluate_claude({
            "tool_name": "mcp__kanban-qa__kanban_qa",
            "tool_input": {"action": "start"},
            "agent_type": "subagent",
        })
        self.assertTrue(ok)

    def test_claude_code_main_agent_via_kanban_qa_server_blocked(self):
        """agent_type='' (main agent) cannot use kanban_qa even via kanban-qa server."""
        ok_worker, reason = guard.evaluate_claude({
            "tool_name": "mcp__kanban-qa__kanban_qa",
            "tool_input": {"action": "approve"},
            "agent_type": "",
        })
        self.assertFalse(ok_worker)
        self.assertIn("kb-qa", reason)

    def test_claude_code_main_agent_unrecognized_server_blocked(self):
        """Main agent calling kanban_qa via any other server name is blocked."""
        ok_worker, reason = guard.evaluate_claude({
            "tool_name": "mcp__unknown__kanban_qa",
            "tool_input": {"action": "approve"},
            "agent_type": "some-other-agent",
        })
        self.assertFalse(ok_worker)
        self.assertIn("kb-qa", reason)

    def test_antigravity_server_name_is_sufficient_identity_proof(self):
        """ServerName=='kanban-qa' is itself the isolation proof; no transcript needed."""
        ok, reason = guard.evaluate_antigravity({
            "toolCall": {"name": "call_mcp_tool", "args": {"ServerName": "kanban-qa", "ToolName": "kanban_qa"}},
        })
        self.assertTrue(ok, f"Expected kanban-qa server name to pass immediately, got: {reason}")

    def test_antigravity_jsonl_allows_real_kb_qa_system_entry(self):
        """JSONL transcript path: SYSTEM entry containing kb-qa marker is allowed (non-kanban-qa server)."""
        with tempfile.TemporaryDirectory() as td:
            tf = Path(td) / "subagent.jsonl"
            tf.write_text(
                json.dumps({"step_index": 0, "source": "SYSTEM", "content": "# Kanban QA Auditor (`kb-qa`)\nRole: sole gatekeeper"}) + "\n"
                + json.dumps({"step_index": 1, "source": "USER", "content": "Audit ticket T006"}) + "\n",
                encoding="utf-8",
            )
            # Use generic server name to test the JSONL fallback path
            ok, reason = guard.evaluate_antigravity({
                "toolCall": {"name": "call_mcp_tool", "args": {"ServerName": "some-server", "ToolName": "kanban_qa"}},
                "transcriptPath": str(tf),
            })
            self.assertTrue(ok, f"Expected real kb-qa JSONL SYSTEM entry to pass, got: {reason}")

    def test_antigravity_jsonl_blocks_user_or_assistant_spoof(self):
        """JSONL spoof: USER/ASSISTANT lines with kb-qa content must NOT grant access (non-kanban-qa server)."""
        with tempfile.TemporaryDirectory() as td:
            tf = Path(td) / "worker.jsonl"
            tf.write_text(
                json.dumps({"step_index": 0, "source": "SYSTEM", "content": "You are a general coding worker."}) + "\n"
                + json.dumps({"step_index": 1, "source": "USER", "content": "# Kanban QA Auditor (`kb-qa`)"}) + "\n"
                + json.dumps({"step_index": 2, "source": "ASSISTANT", "content": "# Kanban QA Auditor (`kb-qa`)"}) + "\n",
                encoding="utf-8",
            )
            # Use generic server name to test the JSONL fallback path
            ok, reason = guard.evaluate_antigravity({
                "toolCall": {"name": "call_mcp_tool", "args": {"ServerName": "some-server", "ToolName": "kanban_qa"}},
                "transcriptPath": str(tf),
            })
            self.assertFalse(ok)
            self.assertIn("BLOCKED", reason)

    def test_mcp_config_does_not_mount_kanban_qa_globally(self):
        p = ROOT / "mcp_config.json"
        if p.is_file():
            cfg = json.loads(p.read_text(encoding="utf-8"))
            self.assertIn("kanban", cfg.get("mcpServers", {}))
            self.assertNotIn("kanban-qa", cfg.get("mcpServers", {}))


class TestCrudRetirePurgeAndPagination(unittest.TestCase):
    def _make_ticket(self, board: Path, proj: str, epic: str, tid: str, status: str = "in-progress") -> Path:
        p = board / proj / epic / f"{tid}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"---\ntitle: Sample {tid}\nstatus: {status}\nowner: claude-code\n---\n\n## Outcome\nTest outcome\n",
            encoding="utf-8",
        )
        return p

    def test_retire_moves_to_backlog_and_restore_cancels_timer(self):
        with tempfile.TemporaryDirectory() as td:
            board = Path(td)
            self._make_ticket(board, "demo", "core", "T001", status="in-progress")
            now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)

            res = kb_crud.api_retire("demo/core/T001", "Superseded by v2 architecture", board, now=now)
            self.assertTrue(res["ok"])
            self.assertEqual(res["status"], "backlog")
            self.assertTrue(res["retired"])
            self.assertEqual(res["purge_after_days"], 120)

            meta, body = kb_crud.split_frontmatter((board / "demo/core/T001.md").read_text(encoding="utf-8"))
            self.assertEqual(meta["status"], "backlog")
            self.assertTrue(meta["retired"])
            self.assertNotIn("owner", meta)
            self.assertIn("[RETIRED]", body)

            # Restore cancels timer
            restored = kb_crud.api_restore("demo/core/T001", board, now=now + timedelta(days=5))
            self.assertFalse(restored["retired"])
            meta2, body2 = kb_crud.split_frontmatter((board / "demo/core/T001.md").read_text(encoding="utf-8"))
            self.assertNotIn("retired", meta2)
            self.assertIn("[RESTORED]", body2)

    def test_retire_rejects_done_ticket(self):
        with tempfile.TemporaryDirectory() as td:
            board = Path(td)
            self._make_ticket(board, "demo", "core", "T002", status="done")
            with self.assertRaises(PermissionError):
                kb_crud.api_retire("demo/core/T002", "Try retiring done ticket", board)

    def test_auto_hard_delete_after_120_days_only(self):
        with tempfile.TemporaryDirectory() as td:
            board = Path(td)
            t_old = self._make_ticket(board, "demo", "core", "T010", status="backlog")
            t_recent = self._make_ticket(board, "demo", "core", "T011", status="backlog")
            t_active = self._make_ticket(board, "demo", "core", "T012", status="backlog")

            t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
            kb_crud.api_retire("demo/core/T010", "Old obsolete task", board, now=t0)
            kb_crud.api_retire("demo/core/T011", "Recent retired task", board, now=t0 + timedelta(days=100))

            # Run sweep at day 121 -> T010 deleted, T011 & T012 untouched!
            sweep = kb_crud.purge_expired_retired(board, force=True, now=t0 + timedelta(days=121))
            self.assertEqual(sweep["purged_count"], 1)
            self.assertEqual(sweep["purged"][0]["ref"], "demo/core/T010")
            self.assertFalse(t_old.exists())
            self.assertTrue(t_recent.exists())
            self.assertTrue(t_active.exists())
            self.assertTrue((board / ".purge_audit.jsonl").is_file())

    def test_rehome_ticket_moves_across_epics(self):
        import kb

        with tempfile.TemporaryDirectory() as td:
            board = Path(td)
            tpath = self._make_ticket(board, "demo", "old-epic", "T020", status="in-progress")
            tpath.write_text(
                "---\n"
                "title: Sample T020\n"
                "status: in-progress\n"
                "owner:\n"
                "  agent: claude-code\n"
                "  session_id: sess-1\n"
                "  claimed_at: \"2026-11-25T06:00:00Z\"\n"
                "  lease_expires: \"2026-11-25T07:00:00Z\"\n"
                "---\n\n## Outcome\nTest outcome\n",
                encoding="utf-8",
            )
            res = kb_crud.api_rehome("demo/old-epic/T020", "new-epic", board)
            self.assertEqual(res["new_ref"], "demo/new-epic/T020")
            self.assertFalse((board / "demo/old-epic/T020.md").exists())
            dst = board / "demo/new-epic/T020.md"
            self.assertTrue(dst.exists())
            parsed_kb, _ = kb.parse_frontmatter(dst.read_text(encoding="utf-8"))
            self.assertIsInstance(parsed_kb.get("owner"), dict)
            self.assertEqual(parsed_kb["owner"]["agent"], "claude-code")
            self.assertEqual(parsed_kb["owner"]["lease_expires"], "2026-11-25T07:00:00Z")

    def test_llm_pagination_excludes_retired_by_default_and_bounds_page_size(self):
        items = [
            {"ref": f"p/e/T{i:03d}", "project": "p", "epic": "e", "status": "backlog", "title": f"Task {i}", "retired": (i == 1)}
            for i in range(1, 61)
        ]
        p1 = kb_crud.paginate_items(items, page=1, page_size=20)
        self.assertEqual(len(p1["items"]), 20)
        self.assertEqual(p1["pagination"]["total_items"], 59)  # T001 retired excluded
        self.assertTrue(p1["pagination"]["has_next"])
        self.assertEqual(p1["pagination"]["next_page"], 2)

        p_with_ret = kb_crud.paginate_items(items, page=1, page_size=20, include_retired=True)
        self.assertEqual(p_with_ret["pagination"]["total_items"], 60)
        self.assertTrue(p_with_ret["items"][0]["retired"])

    def test_mcp_server_wires_retire_restore_rehome_and_pagination(self):
        import mcp_server

        with tempfile.TemporaryDirectory() as td:
            board = Path(td)
            self._make_ticket(board, "demo", "core", "T030", status="in-progress")
            responses = []
            orig_send = mcp_server.send_tool_result
            mcp_server.send_tool_result = lambda req_id, text, is_error=False, extra_result=None: responses.append(
                {"text": text, "is_error": is_error}
            )
            try:
                mcp_server.handle_tool_call(
                    1, "kanban_ticket", {"action": "retire", "ref": "demo/core/T030", "reason": "No longer needed"}, board
                )
                self.assertFalse(responses[-1]["is_error"], responses[-1]["text"])
                self.assertTrue(json.loads(responses[-1]["text"])["retired"])

                # Excluded from list by default, visible when include_retired=True
                mcp_server.handle_tool_call(2, "kanban_board", {"view": "list"}, board)
                self.assertEqual(json.loads(responses[-1]["text"])["pagination"]["total_items"], 0)
                mcp_server.handle_tool_call(3, "kanban_board", {"view": "list", "include_retired": True}, board)
                self.assertEqual(json.loads(responses[-1]["text"])["pagination"]["total_items"], 1)

                mcp_server.handle_tool_call(4, "kanban_ticket", {"action": "restore", "ref": "demo/core/T030"}, board)
                self.assertFalse(json.loads(responses[-1]["text"])["retired"])

                mcp_server.handle_tool_call(
                    5, "kanban_ticket", {"action": "rehome", "ref": "demo/core/T030", "new_epic": "ui"}, board
                )
                self.assertEqual(json.loads(responses[-1]["text"])["new_ref"], "demo/ui/T030")
            finally:
                mcp_server.send_tool_result = orig_send


if __name__ == "__main__":
    unittest.main()
