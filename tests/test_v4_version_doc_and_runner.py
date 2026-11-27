#!/usr/bin/env python3
"""tests/test_v4_version_doc_and_runner.py — Positive + Negative (Pluto) tests for KanbanBoard v4.0."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import kb_version
import kb_doc_store
import kb_doc_runner


def _write_ticket(board: Path, project: str, epic: str, tid: str, title: str, status: str = "done", files=None) -> Path:
    epic_dir = board / project / epic
    epic_dir.mkdir(parents=True, exist_ok=True)
    p = epic_dir / f"{tid}-sample.md"
    files_yaml = ", ".join(files or [])
    p.write_text(
        f"---\nid: {tid}\ntitle: {title}\nstatus: {status}\nfiles: [{files_yaml}]\n---\n\n# {title}\nDone body.\n",
        encoding="utf-8",
    )
    return p


class TestV4SemVerAndClustering(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.board = Path(self.tmp.name) / "board"
        (self.board / "alpha").mkdir(parents=True)
        (self.board / "alpha" / "project.md").write_text("---\nname: alpha\n---\n# Alpha\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_semver_monotonic_positive_and_negative(self):
        self.assertTrue(kb_version.is_version_increase("V1.0.0", "V1.0.1"))
        self.assertTrue(kb_version.is_version_increase("V1.0.0", "V2.0.0"))
        # Pluto negative checks: equal, lower, malformed
        self.assertFalse(kb_version.is_version_increase("V1.0.0", "V1.0.0"))
        self.assertFalse(kb_version.is_version_increase("V2.0.0", "V1.9.9"))
        with self.assertRaises(ValueError):
            kb_version.parse_semver("vNext")

    def test_n_minus_1_accounting_preserves_signed_ticket_files(self):
        t1 = _write_ticket(self.board, "alpha", "search", "T001", "Search tokenizer", files=["src/search.py"])
        t1_before = t1.read_text(encoding="utf-8")
        res1 = kb_version.bump_project_version(self.board, "alpha", "V1.0.0", bumped_by="agent")
        self.assertEqual(res1["shipped_tickets"], ["alpha/search/T001"])
        # Signed done ticket file was NOT mutated
        self.assertEqual(t1.read_text(encoding="utf-8"), t1_before)
        # New ticket done while at V1.0.0 belongs to V_next (n - 1 rule)
        _write_ticket(self.board, "alpha", "search", "T002", "Search ranker", files=["src/search.py"])
        pending = kb_version.get_pending_done_tickets(self.board, "alpha")
        self.assertEqual([t["ref"] for t in pending], ["alpha/search/T002"])
        # Pluto negative: cannot bump to equal or lower version
        with self.assertRaises(ValueError):
            kb_version.bump_project_version(self.board, "alpha", "V1.0.0")

    def test_disjoint_clustering_and_smart_snooze(self):
        # 6 tickets in 'search' epic -> below threshold (7) -> no nudge
        for i in range(1, 7):
            _write_ticket(self.board, "alpha", "search", f"T00{i}", f"Search engine part {i}", files=["src/search/core.py"])
        self.assertIsNone(kb_version.evaluate_version_nudge(self.board, "alpha"))

        # 7th ticket crosses >= 7 cluster threshold -> fires nudge
        _write_ticket(self.board, "alpha", "search", "T007", "Search engine part 7", files=["src/search/core.py"])
        nudge1 = kb_version.evaluate_version_nudge(self.board, "alpha")
        self.assertIsNotNone(nudge1)
        self.assertEqual(nudge1["trigger"], "cluster")
        self.assertEqual(nudge1["largest_cluster"]["size"], 7)

        # +1 ticket into same largest cluster (size 8) -> snoozed (needs +2)
        _write_ticket(self.board, "alpha", "search", "T008", "Search engine part 8", files=["src/search/core.py"])
        self.assertIsNone(kb_version.evaluate_version_nudge(self.board, "alpha"))

        # +2nd ticket into same largest cluster (size 9) -> re-triggers!
        _write_ticket(self.board, "alpha", "search", "T009", "Search engine part 9", files=["src/search/core.py"])
        nudge2 = kb_version.evaluate_version_nudge(self.board, "alpha")
        self.assertIsNotNone(nudge2)
        self.assertEqual(nudge2["largest_cluster"]["size"], 9)

        # Build a NEW bigger cluster (10 tickets in 'billing') -> immediately re-triggers even without +2 on search!
        for i in range(10, 20):
            _write_ticket(self.board, "alpha", "billing", f"T0{i}", f"Billing invoice {i}", files=["src/billing/inv.py"])
        nudge3 = kb_version.evaluate_version_nudge(self.board, "alpha")
        self.assertIsNotNone(nudge3)
        self.assertEqual(nudge3["largest_cluster"]["size"], 10)

        # Verify strict disjointness: every pending ticket appears in exactly 1 cluster
        pending = kb_version.get_pending_done_tickets(self.board, "alpha")
        clusters = kb_version.cluster_tickets(pending)
        seen = []
        for c in clusters:
            seen.extend(c["tickets"])
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(seen), {t["ref"] for t in pending})

    def test_scattered_safety_net_12(self):
        # 12 unrelated epics/files -> largest cluster = 1, total = 12 -> fires scattered_total
        for i in range(1, 13):
            _write_ticket(self.board, "alpha", f"ep{i}", f"T{i:03d}", f"Unrelated chore {i}", files=[f"pkg{i}/m{i}.py"])
        nudge = kb_version.evaluate_version_nudge(self.board, "alpha")
        self.assertIsNotNone(nudge)
        self.assertEqual(nudge["trigger"], "scattered_total")
        self.assertEqual(nudge["total_pending_done"], 12)


class TestV4DocStoreAndSterilizedRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.board = Path(self.tmp.name) / "board"
        (self.board / "alpha").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_containerized_doc_crud_sanitization_and_pluto_slug(self):
        meta = kb_doc_store.upsert_section(
            self.board, "alpha", "auth-flow",
            title="Auth Flow",
            tell_html='<article onclick="evil()"><h2>Auth</h2><script>alert(1)</script></article>',
            version="V1.0.0",
            source_tickets=["alpha/auth/T001"],
        )
        self.assertEqual(meta["tell_version"], "V1.0.0")
        sec = kb_doc_store.read_section(self.board, "alpha", "auth-flow")
        self.assertNotIn("<script>", sec["tell_html"])
        self.assertNotIn("onclick", sec["tell_html"])
        # Pluto negative: path traversal slug and project rejected
        with self.assertRaises(ValueError):
            kb_doc_store.validate_slug("../escape")
        with self.assertRaises(ValueError):
            kb_doc_store.doc_root(self.board, "../escape")
        with self.assertRaises(ValueError):
            kb_version.bump_project_version(self.board, "../escape", "V1.0.0")

        # Pluto negative: unquoted event handler & javascript: URI stripped
        san = kb_doc_store.sanitize_tell_html('<a href=javascript:alert(1) onmouseover=evil()>bad</a>')
        self.assertNotIn("javascript:", san.lower())
        self.assertNotIn("onmouseover", san.lower())

    def test_feedback_120_day_purge_never_deletes_open(self):
        fb_open = kb_doc_store.add_feedback(self.board, "alpha", "Clarify Pluto negative test", section="auth-flow")
        fb_old_res = kb_doc_store.add_feedback(self.board, "alpha", "Fix typo in header", section="auth-flow")
        kb_doc_store.resolve_feedback(self.board, "alpha", fb_old_res["id"], "V1.0.0", "Fixed")

        # Simulate 130 days later: old resolved should purge, open MUST stay
        future = datetime.now(timezone.utc) + timedelta(days=130)
        purged = kb_doc_store.purge_expired_feedback(self.board, "alpha", retention_days=120, now=future)
        self.assertEqual(purged, 1)
        remaining = kb_doc_store.list_feedback(self.board, "alpha")
        self.assertEqual([x["id"] for x in remaining], [fb_open["id"]])

    def test_sterilized_cli_invocation_and_automatic_fallback(self):
        inv_agy = kb_doc_runner.build_cli_invocation("agy", "gemini-4-hydrogen-medium", 150, self.board, "hello")
        self.assertEqual(inv_agy["env"]["KANBAN_INTERNAL"], "1")
        self.assertTrue(inv_agy["env"]["USERPROFILE"].endswith("_doc_home"))
        self.assertTrue(inv_agy["cwd"].endswith("_doc_sandbox"))
        self.assertIn("--disable-slash-commands", inv_agy["argv"])
        self.assertEqual(json.loads(inv_agy["stdin_bytes"].decode("utf-8"))["event"], "user")

        inv_codex = kb_doc_runner.build_cli_invocation("codex", "gpt-6-luna", 150, self.board, "hello")
        self.assertIn("--ignore-user-config", inv_codex["argv"])
        self.assertIn("--ignore-rules", inv_codex["argv"])
        self.assertIn("read-only", inv_codex["argv"])

        # Simulate agy failing -> automatic fallback to codex succeeds and writes section
        calls = []
        def fake_exec(inv, timeout):
            calls.append(inv["backend"])
            if inv["backend"] == "agy":
                return 1, "", "agy unavailable"
            return 0, json.dumps({
                "upsert_sections": [{
                    "slug": "overview",
                    "title": "Architecture Overview",
                    "summary": "Core modules",
                    "tell_html": "<article><h2>Overview</h2><p>Sterilized.</p></article>",
                    "source_tickets": ["alpha/core/T001"],
                }],
                "delete_sections": [],
                "resolve_feedback": [],
            }), ""

        res = kb_doc_runner.run_tell_update(self.board, "alpha", "V1.0.0", ["alpha/core/T001"], executor=fake_exec)
        self.assertTrue(res["ok"])
        self.assertEqual(calls, ["agy", "codex"])
        self.assertEqual(res["backend_used"], "codex")
        self.assertTrue(res["fallback_used"])
        sec = kb_doc_store.read_section(self.board, "alpha", "overview")
        self.assertEqual(sec["meta"]["tell_version"], "V1.0.0")

    def test_agy_stream_json_prefers_result_over_deltas(self):
        ndjson = "\n".join([
            json.dumps({"event": "delta", "message": {"content": '{"partial":'}}),
            json.dumps({"event": "result", "message": {"content": '{"upsert_sections": []}'}}),
        ])
        extracted = kb_doc_runner._extract_agy_stream_text(ndjson)
        self.assertEqual(kb_doc_runner.extract_json_object(extracted), {"upsert_sections": []})


class TestV4McpViewerAndCspIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.board = Path(self.tmp.name) / "board"
        (self.board / "alpha").mkdir(parents=True)
        (self.board / "alpha" / "project.md").write_text("---\nname: alpha\n---\n# Alpha\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_mcp_kanban_project_and_non_qa_version_nudge(self):
        import mcp_server

        for i in range(1, 8):
            _write_ticket(self.board, "alpha", "search", f"T{i:03d}", f"Search feature {i}", files=["src/search.py"])

        captured = []
        orig_send = mcp_server.send_tool_result
        mcp_server.send_tool_result = lambda req_id, text, is_error=False, extra_result=None: captured.append((text, is_error))
        try:
            # Work mode overview surfaces version_nudge
            mcp_server.handle_tool_call(1, "kanban_board", {"view": "overview", "project": "alpha"}, self.board, mode="work")
            self.assertFalse(captured[-1][1], captured[-1][0])
            ov = json.loads(captured[-1][0])
            self.assertIn("version_nudge", ov["projects"][0])
            self.assertEqual(ov["projects"][0]["version_nudge"]["trigger"], "cluster")

            # QA mode MUST NEVER surface version_nudge on kanban_board
            mcp_server.handle_tool_call(2, "kanban_board", {"view": "overview", "project": "alpha"}, self.board, mode="qa")
            self.assertFalse(captured[-1][1], captured[-1][0])
            ov_qa = json.loads(captured[-1][0])
            self.assertNotIn("version_nudge", ov_qa["projects"][0])

            # Bump version via kanban_project without spawning CLI thread
            mcp_server.handle_tool_call(
                3,
                "kanban_project",
                {"action": "bump_version", "project": "alpha", "version": "V1.0.0", "run_doc": False, "note": "Initial ship"},
                self.board,
                mode="work",
            )
            self.assertFalse(captured[-1][1], captured[-1][0])
            bump = json.loads(captured[-1][0])
            self.assertEqual(bump["new_version"], "V1.0.0")
            self.assertEqual(bump["ticket_count"], 7)

            # History check
            mcp_server.handle_tool_call(4, "kanban_project", {"action": "version_history", "project": "alpha"}, self.board)
            hist = json.loads(captured[-1][0])
            self.assertEqual(hist["version"], "V1.0.0")
            self.assertEqual(len(hist["history"]), 1)
        finally:
            mcp_server.send_tool_result = orig_send

    def test_viewer_v4_routes_and_strict_csp_assets(self):
        import threading
        import urllib.error
        import urllib.request
        import viewer

        kb_doc_store.upsert_section(
            self.board,
            "alpha",
            "architecture",
            title="Architecture",
            tell_html="<article><h2>Arch</h2></article>",
            show_js="export function mountShow(c, e, m) { return { destroy() {} }; }",
            version="V1.0.0",
        )
        server, port = viewer.find_available_server(self.board, preferred_port=8960)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        base = f"http://127.0.0.1:{port}"
        try:
            for asset in ("/doc-shared/base.css", "/doc-shared/shell.js", "/assets/v4_nav.css", "/assets/v4_nav.js"):
                with urllib.request.urlopen(f"{base}{asset}") as res:
                    self.assertEqual(res.status, 200)

            with urllib.request.urlopen(f"{base}/api/doc/show.js?project=alpha&slug=architecture") as res:
                self.assertEqual(res.status, 200)
                self.assertIn("javascript", res.headers.get("Content-Type", ""))
                self.assertIn("mountShow", res.read().decode("utf-8"))

            # Pluto negative: POST without CSRF token blocked with 403
            req = urllib.request.Request(
                f"{base}/api/doc/config",
                data=b'{"scope":"global","config":{"snooze_delta":3}}',
                headers={"Content-Type": "application/json", "Origin": base},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req)
            self.assertEqual(ctx.exception.code, 403)
        finally:
            server.server_close()

        # Verify strict-CSP discipline on UI scripts
        shell_js = (ROOT / "doc_shared" / "shell.js").read_text(encoding="utf-8")
        nav_js = (ROOT / "resources" / "v4_nav.js").read_text(encoding="utf-8")
        self.assertNotIn("URL.createObjectURL", shell_js)
        self.assertNotIn("style=", shell_js)
        self.assertNotIn("style=", nav_js)


if __name__ == "__main__":
    unittest.main()
