#!/usr/bin/env python3
"""tests/test_v401_queue_export_and_diagram.py — Positive + Pluto Negative tests for KanbanBoard v4.0.1."""
from __future__ import annotations

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
import kb_doc_queue
import kb_stack_diagram
import kb_doc_export
import kb_doc_v401


def _write_ticket(board: Path, project: str, epic: str, tid: str, title: str, files=None) -> None:
    d = board / project / epic
    d.mkdir(parents=True, exist_ok=True)
    fstr = ", ".join(files or [])
    (d / f"{tid}-item.md").write_text(
        f"---\nid: {tid}\ntitle: {title}\nstatus: done\nfiles: [{fstr}]\n---\n\n# {title}\n",
        encoding="utf-8",
    )


class TestV401QueueDiagramExportAndDrift(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.board = Path(self.tmp.name) / "board"
        (self.board / "alpha").mkdir(parents=True)
        (self.board / "alpha" / "project.md").write_text("---\nname: alpha\n---\n# Alpha\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_global_queue_coalescing_rate_limit_defer_and_recovery(self):
        # Coalesce two queued TELL jobs for the same project
        j1 = kb_doc_queue.enqueue_job(self.board, project="alpha", mode="tell", version="V1.0.0", shipped_tickets=["alpha/core/T001"])
        j2 = kb_doc_queue.enqueue_job(self.board, project="alpha", mode="tell", version="V1.1.0", shipped_tickets=["alpha/core/T002"])
        self.assertEqual(j1["id"], j2["id"])
        self.assertEqual(j2["version"], "V1.1.0")
        self.assertEqual(j2["shipped_tickets"], ["alpha/core/T001", "alpha/core/T002"])

        # Pluto negative: invalid mode and SHOW without slug rejected
        with self.assertRaises(ValueError):
            kb_doc_queue.enqueue_job(self.board, project="alpha", mode="bogus")
        with self.assertRaises(ValueError):
            kb_doc_queue.enqueue_job(self.board, project="alpha", mode="show", slug=None)

        # Simulate rate limit -> job becomes deferred (NOT lost/failed) with backoff
        t0 = datetime(2026, 11, 27, 10, 0, 0, tzinfo=timezone.utc)
        out = kb_doc_queue.process_next_job(
            self.board,
            lambda b, j: {"ok": False, "error": "HTTP 429 rate limit exceeded"},
            now=t0,
        )
        self.assertEqual(out["status"], "deferred")
        self.assertEqual(out["retries"], 1)
        # Before backoff expires -> process_next_job returns None
        self.assertIsNone(kb_doc_queue.process_next_job(self.board, lambda b, j: {"ok": True}, now=t0 + timedelta(seconds=30)))
        # After backoff expires -> succeeds!
        done = kb_doc_queue.process_next_job(self.board, lambda b, j: {"ok": True, "run_id": "r1"}, now=t0 + timedelta(seconds=130))
        self.assertEqual(done["status"], "done")

    def test_stack_diagram_orthogonal_and_xss_escaping(self):
        spec = {
            "title": "Alpha <script>alert(1)</script>",
            "groups": [
                {"id": "g1", "label": "Clients", "tone": "default", "nodes": [{"id": "web", "title": "Web App", "subtitle": "CSP", "icon": "browser"}]},
                {"id": "g2", "label": "Core", "tone": "core", "nodes": [{"id": "api", "title": "Python API", "subtitle": "stdlib", "icon": "python"}]},
            ],
            "edges": [{"from": "web", "to": "api", "label": "HTTPS/CSRF", "tone": "amber"}],
        }
        frag = kb_stack_diagram.render_stack_diagram_fragment(spec, board=self.board)
        self.assertIn('data-sd-theme="light"', frag)
        self.assertNotIn("<script>", frag)
        self.assertIn("HTTPS/CSRF", frag)
        # Pluto negative: empty groups rejected
        with self.assertRaises(ValueError):
            kb_stack_diagram.render_stack_diagram_svg({"title": "Empty", "groups": []})

    def test_rollback_snapshots_and_formal_tell_pdf_html(self):
        kb_doc_store.upsert_section(
            self.board, "alpha", "done-gate",
            title="Three-Wall Done Gate",
            tell_html="<p>Version 1 content.</p>",
            version="V1.0.0",
            source_tickets=["alpha/sec/T001"],
        )
        snap_id = kb_doc_v401.snapshot_section(self.board, "alpha", "done-gate")
        self.assertIsNotNone(snap_id)
        kb_doc_store.upsert_section(
            self.board, "alpha", "done-gate",
            title="Three-Wall Done Gate",
            tell_html="<p>Accidental bad edit.</p>",
            version="V1.1.0",
        )
        rev = kb_doc_v401.revert_section(self.board, "alpha", "done-gate")
        self.assertTrue(rev["ok"])
        sec = kb_doc_store.read_section(self.board, "alpha", "done-gate")
        self.assertIn("Version 1 content", sec["tell_html"])

        # Formal Snowflake x Wikipedia print HTML has Cover + Dedicated TOC page + Section
        print_html = kb_doc_export.build_formal_tell_print_html(self.board, "alpha")
        self.assertIn("cover-page", print_html)
        self.assertIn("toc-page", print_html)
        self.assertIn("Table of Contents", print_html)
        self.assertIn("Three-Wall Done Gate", print_html)
        # Graceful fallback when headless browser binary is absent
        pdf_res = kb_doc_export.export_tell_pdf(self.board, "alpha", browser_bin="")
        self.assertIn("ok", pdf_res)

    def test_smart_show_drift_context_small_vs_large_gap(self):
        # Create 4 versions: V1.0.0 -> V1.1.0 -> V1.2.0 -> V1.3.0 -> V1.4.0
        for idx, ver in enumerate(["V1.0.0", "V1.1.0", "V1.2.0", "V1.3.0", "V1.4.0"], start=1):
            _write_ticket(self.board, "alpha", "core", f"T00{idx}", f"Feature {idx}", files=[f"src/f{idx}.py"])
            kb_version.bump_project_version(self.board, "alpha", ver, bumped_by="agent")

        # Small gap (SHOW V1.3.0 vs TELL V1.4.0 -> gap = 1 <= 2 -> bounded_delta with existing_show_js)
        kb_doc_store.upsert_section(
            self.board, "alpha", "core-arch",
            title="Core Architecture",
            tell_html="<p>Current V1.4.0 truth.</p>",
            show_js="export function mountShow() {}",
            version="V1.3.0",
            source_tickets=["alpha/core/T004", "alpha/core/T005"],
        )
        kb_doc_store.upsert_section(
            self.board, "alpha", "core-arch",
            title="Core Architecture",
            tell_html="<p>Updated V1.4.0 truth.</p>",
            version="V1.4.0",
            source_tickets=["alpha/core/T004", "alpha/core/T005"],
        )
        ctx_small = kb_doc_v401.build_show_context_v401(self.board, "alpha", "core-arch")
        self.assertEqual(ctx_small["strategy"], "bounded_delta")
        self.assertEqual(ctx_small["version_gap"], 1)
        self.assertIsNotNone(ctx_small["existing_show_js"])

        # Large gap (SHOW V1.0.0 vs TELL V1.4.0 -> gap = 4 > 2 -> fresh_current_state, omits stale show.js)
        meta_path = kb_doc_store.doc_root(self.board, "alpha") / "sections" / "core-arch" / "meta.json"
        import json
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["show_version"] = "V1.0.0"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        ctx_large = kb_doc_v401.build_show_context_v401(self.board, "alpha", "core-arch")
        self.assertEqual(ctx_large["strategy"], "fresh_current_state")
        self.assertEqual(ctx_large["version_gap"], 4)
        self.assertIsNone(ctx_large["existing_show_js"])

    def test_runner_integrates_doc_prompts_snapshots_stack_diagram_and_queue(self):
        import json
        import kb_doc_runner

        _write_ticket(self.board, "alpha", "core", "T001", "Gate architecture", files=["kb.py"])
        tell_prompt = kb_doc_runner.build_tell_prompt(self.board, "alpha", "V1.0.0", ["alpha/core/T001"])
        self.assertIn("TELL Authoring Guide", tell_prompt)

        def fake_tell_v1(inv, timeout):
            return 0, json.dumps({
                "upsert_sections": [{
                    "slug": "architecture",
                    "parent_section": "Core Engine",
                    "title": "Architecture Overview",
                    "summary": "Core v1",
                    "order": 0,
                    "source_tickets": ["alpha/core/T001"],
                    "stack_diagram": {
                        "title": "Core Stack",
                        "groups": [{"id": "g1", "label": "Core", "tone": "core", "nodes": [{"id": "kb", "title": "kb.py", "icon": "python"}]}],
                        "edges": [],
                    },
                    "tell_html": "<article><h2>V1</h2><p>Initial.</p></article>",
                }],
                "delete_sections": [],
                "resolve_feedback": [],
            }), ""

        res1 = kb_doc_runner.run_queued_job(
            self.board,
            {"mode": "tell", "project": "alpha", "version": "V1.0.0", "shipped_tickets": ["alpha/core/T001"]},
            executor=fake_tell_v1,
        )
        self.assertTrue(res1["ok"])
        sec1 = kb_doc_store.read_section(self.board, "alpha", "architecture")
        self.assertEqual(sec1["meta"]["parent_section"], "Core Engine")
        self.assertIn("stack-diagram", sec1["diagram_html"])

        # Second TELL update auto-snapshots V1 before writing V2
        def fake_tell_v2(inv, timeout):
            return 0, json.dumps({
                "upsert_sections": [{
                    "slug": "architecture",
                    "parent_section": "Core Engine",
                    "title": "Architecture Overview",
                    "summary": "Core v2",
                    "tell_html": "<article><h2>V2</h2><p>Updated.</p></article>",
                }],
                "delete_sections": [],
                "resolve_feedback": [],
            }), ""

        res2 = kb_doc_runner.run_queued_job(
            self.board,
            {"mode": "tell", "project": "alpha", "version": "V1.1.0", "shipped_tickets": []},
            executor=fake_tell_v2,
        )
        self.assertTrue(res2["ok"])
        snaps = kb_doc_v401.list_snapshots(self.board, "alpha", "architecture")
        self.assertEqual(len(snaps), 1)
        kb_doc_v401.revert_section(self.board, "alpha", "architecture")
        reverted = kb_doc_store.read_section(self.board, "alpha", "architecture")
        self.assertIn("Initial.", reverted["tell_html"])

        show_prompt = kb_doc_runner.build_show_prompt(self.board, "alpha", "architecture")
        self.assertIn("SHOW Authoring Guide", show_prompt)

        def fake_show(inv, timeout):
            return 0, json.dumps({
                "show_js": "export function mountShow(c, e, m) { return { destroy() {} }; }",
                "show_subtitle": "How Core Routes Work",
                "show_companion_html": "<p>Another angle.</p><script>bad()</script>",
                "resolve_feedback": [],
            }), ""

        sres = kb_doc_runner.run_queued_job(
            self.board,
            {"mode": "show", "project": "alpha", "slug": "architecture"},
            executor=fake_show,
        )
        self.assertTrue(sres["ok"])
        sec_after_show = kb_doc_store.read_section(self.board, "alpha", "architecture")
        self.assertEqual(sec_after_show["meta"]["show_subtitle"], "How Core Routes Work")
        self.assertNotIn("<script>", sec_after_show["meta"]["show_companion_html"])

    def test_viewer_v401_queue_export_csp_and_revert_endpoints(self):
        import json
        import threading
        import urllib.error
        import urllib.request
        import viewer

        kb_doc_store.upsert_section(
            self.board,
            "alpha",
            "overview",
            title="Overview",
            parent_section="Architecture",
            tell_html="<article><h2>Overview</h2><p>Strict CSP print test.</p></article>",
            version="V1.0.0",
        )
        server, port = viewer.find_available_server(self.board, preferred_port=8970)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        base = f"http://127.0.0.1:{port}"
        try:
            with urllib.request.urlopen(f"{base}/health") as res:
                h = json.loads(res.read().decode("utf-8"))
                self.assertEqual(h["version"], "4.0.1")

            with urllib.request.urlopen(f"{base}/api/doc/export/print.css") as res:
                self.assertEqual(res.status, 200)
                self.assertIn("text/css", res.headers.get("Content-Type", ""))

            with urllib.request.urlopen(f"{base}/api/doc/export/print-html?project=alpha") as res:
                self.assertEqual(res.status, 200)
                phtml = res.read().decode("utf-8")
                self.assertIn("/api/doc/export/print.css", phtml)
                self.assertNotIn("<style>", phtml)

            # Enqueue SHOW -> 202 Accepted cleanly
            req_show = urllib.request.Request(
                f"{base}/api/doc/show/generate",
                data=json.dumps({"project": "alpha", "slug": "overview"}).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Origin": base,
                    "X-Kanban-CSRF": server.csrf_token,
                },
                method="POST",
            )
            with urllib.request.urlopen(req_show) as res:
                self.assertEqual(res.status, 202)
                sdata = json.loads(res.read().decode("utf-8"))
                self.assertEqual(sdata["job"]["mode"], "show")

            # Pluto negative: revert without snapshots returns 400
            req_rev = urllib.request.Request(
                f"{base}/api/doc/revert",
                data=json.dumps({"project": "alpha", "slug": "overview"}).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Origin": base,
                    "X-Kanban-CSRF": server.csrf_token,
                },
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req_rev)
            self.assertEqual(ctx.exception.code, 400)
        finally:
            server.server_close()

        # Verify strict-CSP discipline and invisible skill migration
        for asset in (
            ROOT / "doc_shared" / "shell.js",
            ROOT / "doc_shared" / "cinema-engine.js",
            ROOT / "resources" / "v4_nav.js",
            ROOT / "resources" / "board.js",
        ):
            txt = asset.read_text(encoding="utf-8")
            self.assertNotIn("style=", txt, f"Found forbidden inline style= in {asset.name}")
        self.assertFalse((ROOT / "skills" / "kanban-doc" / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
