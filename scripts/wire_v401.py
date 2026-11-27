#!/usr/bin/env python3
"""scripts/wire_v401.py — Idempotently wires KanbanBoard v4.0.1 upgrades on top of v4.0 (commit 3b3b074).

Changes applied:
  1. viewer.py:
     - Imports kb_doc_queue, kb_doc_v401, kb_doc_export, kb_stack_diagram.
     - Adds GET routes: /api/doc/status, /api/doc/snapshots, /api/doc/export/html,
       /api/doc/export/print-html, /api/doc/export/pdf.
     - Adds CSRF-protected POST routes: /api/doc/tell/refresh, /api/doc/revert, /api/doc/queue/retry.
     - Switches /api/version/bump and /api/doc/show/generate to enqueue onto the global persistent
       single-worker `kb_doc_queue` (non-blocking HTTP, crash-safe, rate-limit deferred retry).
     - Excludes `_doc_queue.jsonl` and `_doc_logo_cache` from board_stamp() if present.
     - Bumps version banner to 4.0.1.
  2. Removes `skills/kanban-doc/SKILL.md` on `--apply` (migrated to internal `doc_prompts/` so
     Claude Code / Antigravity main agents cannot auto-discover or invoke kb-doc).
  3. Bumps `.claude-plugin/plugin.json` and `plugin.json` to 4.0.1.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def patch_viewer(src: str) -> str:
    out = src
    if "import kb_doc_queue" not in out and "import kb_doc_runner\n" in out:
        out = out.replace(
            "import kb_doc_runner\n",
            "import kb_doc_runner\nimport kb_doc_queue\nimport kb_doc_v401\nimport kb_doc_export\n",
            1,
        )
    out = out.replace('"version": "4.0.0"', '"version": "4.0.1"')
    out = out.replace('"KanbanViewer/4.0"', '"KanbanViewer/4.0.1"')
    out = out.replace("Kanban Board Viewer v4.0 running", "Kanban Board Viewer v4.0.1 running")

    if '("_doc_sandbox", "_doc_home")' in out:
        out = out.replace(
            '("_doc_sandbox", "_doc_home")',
            '("_doc_sandbox", "_doc_home", "_doc_logo_cache")',
            1,
        )

    # Wire KanbanServer queue background worker start/stop
    if "kb_doc_queue.start_background_worker" not in out and "self.cache = BoardCache(board)\n" in out:
        out = out.replace(
            "self.cache = BoardCache(board)\n",
            "self.cache = BoardCache(board)\n        kb_doc_queue.start_background_worker(board, kb_doc_runner.run_queued_job)\n",
            1,
        )
    if "kb_doc_queue.stop_background_worker" not in out and "self.closing.set()\n" in out:
        out = out.replace(
            "self.closing.set()\n",
            "self.closing.set()\n        kb_doc_queue.stop_background_worker(timeout=1.5)\n",
            1,
        )

    # Add v4.0.1 GET routes right before `if path == "/api/doc/manifest":`
    if 'path == "/api/doc/status"' not in out and 'if path == "/api/doc/manifest":' in out:
        v401_gets = (
            'if path == "/api/doc/status":\n'
            '            proj = (qs.get("project") or [""])[0].strip() or None\n'
            '            return self._json(200, kb_doc_queue.get_queue_status(self.server.board, project=proj), head)\n\n'
            '        if path == "/api/doc/snapshots":\n'
            '            proj = (qs.get("project") or [""])[0].strip()\n'
            '            slug = (qs.get("slug") or [""])[0].strip()\n'
            '            try:\n'
            '                return self._json(200, {"ok": True, "snapshots": kb_doc_v401.list_snapshots(self.server.board, proj, slug)}, head)\n'
            '            except ValueError as e:\n'
            '                return self._json(400, {"ok": False, "error": str(e)}, head)\n\n'
            '        if path == "/api/doc/export/print.css":\n'
            '            return self._send(200, kb_doc_export.FORMAL_PRINT_CSS.encode("utf-8"), "text/css; charset=utf-8", head)\n\n'
            '        if path == "/api/doc/export/html":\n'
            '            proj = (qs.get("project") or [""])[0].strip()\n'
            '            if not proj:\n'
            '                return self._json(400, {"ok": False, "error": "missing project"}, head)\n'
            '            html_doc = kb_doc_export.build_offline_html(self.server.board, proj)\n'
            '            return self._send(200, html_doc.encode("utf-8"), "text/html; charset=utf-8", head)\n\n'
            '        if path == "/api/doc/export/print-html":\n'
            '            proj = (qs.get("project") or [""])[0].strip()\n'
            '            if not proj:\n'
            '                return self._json(400, {"ok": False, "error": "missing project"}, head)\n'
            '            html_doc = kb_doc_export.build_formal_tell_print_html(self.server.board, proj, inline_css=False)\n'
            '            return self._send(200, html_doc.encode("utf-8"), "text/html; charset=utf-8", head)\n\n'
            '        if path == "/api/doc/export/pdf":\n'
            '            proj = (qs.get("project") or [""])[0].strip()\n'
            '            if not proj:\n'
            '                return self._json(400, {"ok": False, "error": "missing project"}, head)\n'
            '            res = kb_doc_export.export_tell_pdf(self.server.board, proj)\n'
            '            if res.get("ok"):\n'
            '                return self._send(200, Path(res["pdf_path"]).read_bytes(), "application/pdf", head)\n'
            '            html_doc = kb_doc_export.build_formal_tell_print_html(self.server.board, proj, inline_css=False)\n'
            '            return self._send(200, html_doc.encode("utf-8"), "text/html; charset=utf-8", head)\n\n'
            '        if path == "/api/doc/manifest":'
        )
        out = out.replace('if path == "/api/doc/manifest":', v401_gets, 1)

    # Expand v4 CSRF-protected POST route tuple and handlers
    old_tuple = 'if path in ("/api/version/bump", "/api/doc/config", "/api/doc/feedback", "/api/doc/show/generate"):'
    new_tuple = 'if path in ("/api/version/bump", "/api/doc/config", "/api/doc/feedback", "/api/doc/show/generate", "/api/doc/tell/refresh", "/api/doc/revert", "/api/doc/queue/retry"):'
    if old_tuple in out:
        out = out.replace(old_tuple, new_tuple, 1)

    # Switch /api/version/bump to use persistent global queue
    old_bump_thread = (
        '                    if cfg.get("auto_tell_on_bump", True):\n'
        '                        threading.Thread(\n'
        '                            target=kb_doc_runner.run_tell_update,\n'
        '                            args=(self.server.board, proj, res["new_version"], res["shipped_tickets"]),\n'
        '                            daemon=True,\n'
        '                        ).start()\n'
        '                    return self._json(200, res, False)'
    )
    new_bump_queue = (
        '                    if cfg.get("auto_tell_on_bump", True):\n'
        '                        res["job"] = kb_doc_queue.enqueue_job(\n'
        '                            self.server.board,\n'
        '                            project=proj,\n'
        '                            mode="tell",\n'
        '                            version=res["new_version"],\n'
        '                            shipped_tickets=res["shipped_tickets"],\n'
        '                            reason="web_version_bump",\n'
        '                        )\n'
        '                    return self._json(200, res, False)'
    )
    if old_bump_thread in out:
        out = out.replace(old_bump_thread, new_bump_queue, 1)

    # Switch /api/doc/show/generate to enqueue cleanly (202 Accepted)
    old_show_post = (
        '                if path == "/api/doc/show/generate":\n'
        '                    res = kb_doc_runner.run_show_generate(\n'
        '                        self.server.board,\n'
        '                        str(payload.get("project") or "").strip(),\n'
        '                        str(payload.get("slug") or "").strip(),\n'
        '                    )\n'
        '                    return self._json(200 if res.get("ok") else 500, res, False)'
    )
    new_show_post = (
        '                if path == "/api/doc/show/generate":\n'
        '                    proj = str(payload.get("project") or "").strip()\n'
        '                    slug = str(payload.get("slug") or "").strip()\n'
        '                    kb_doc_store.read_section(self.server.board, proj, slug)\n'
        '                    job = kb_doc_queue.enqueue_job(\n'
        '                        self.server.board,\n'
        '                        project=proj,\n'
        '                        mode="show",\n'
        '                        slug=slug,\n'
        '                        reason="boss_show_generate",\n'
        '                    )\n'
        '                    return self._json(202, {"ok": True, "job": job}, False)'
    )
    if old_show_post in out:
        out = out.replace(old_show_post, new_show_post, 1)

    if 'path == "/api/doc/tell/refresh"' not in out and 'if path == "/api/doc/show/generate":' in out:
        v401_posts = (
            'if path == "/api/doc/tell/refresh":\n'
            '                    proj = str(payload.get("project") or "").strip()\n'
            '                    vstate = kb_version.load_version_state(self.server.board, proj)\n'
            '                    if vstate.get("version") == "V0.0.0":\n'
            '                        return self._json(400, {"ok": False, "error": "Bump version past V0.0.0 first."}, False)\n'
            '                    job = kb_doc_queue.enqueue_job(self.server.board, project=proj, mode="tell", version=vstate["version"], reason="boss_feedback_refresh")\n'
            '                    return self._json(202, {"ok": True, "job": job}, False)\n'
            '                if path == "/api/doc/revert":\n'
            '                    res = kb_doc_v401.revert_section(self.server.board, str(payload.get("project") or "").strip(), str(payload.get("slug") or "").strip(), payload.get("snapshot_id"))\n'
            '                    return self._json(200, res, False)\n'
            '                if path == "/api/doc/queue/retry":\n'
            '                    job = kb_doc_queue.retry_job_now(self.server.board, str(payload.get("job_id") or "").strip())\n'
            '                    if not job:\n'
            '                        return self._json(404, {"ok": False, "error": "job not found or not retryable"}, False)\n'
            '                    return self._json(200, {"ok": True, "job": job}, False)\n'
            '                if path == "/api/doc/show/generate":'
        )
        out = out.replace('if path == "/api/doc/show/generate":', v401_posts, 1)

    return out


def patch_manifest_version(src: str) -> str:
    return re.sub(r'"version"\s*:\s*"4\.0\.0"', '"version": "4.0.1"', src, count=1)


def show_diff(path: Path, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path.relative_to(ROOT)}",
            tofile=f"b/{path.relative_to(ROOT)}",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Wire KanbanBoard v4.0.1 upgrades")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    targets = [
        (ROOT / "viewer.py", patch_viewer),
        (ROOT / ".claude-plugin" / "plugin.json", patch_manifest_version),
        (ROOT / "plugin.json", patch_manifest_version),
    ]
    for path, fn in targets:
        if not path.is_file():
            print(f"[SKIP] {path.relative_to(ROOT)} not found", file=sys.stderr)
            continue
        old = path.read_text(encoding="utf-8")
        new = fn(old)
        if old == new:
            print(f"[OK] {path.relative_to(ROOT)} already up to date.")
            continue
        print(show_diff(path, old, new))
        if args.apply:
            path.write_text(new, encoding="utf-8", newline="\n")
            print(f"[APPLIED] {path.relative_to(ROOT)}")

    old_skill = ROOT / "skills" / "kanban-doc" / "SKILL.md"
    if old_skill.is_file():
        if args.apply:
            old_skill.unlink()
            print("[REMOVED] skills/kanban-doc/SKILL.md (moved to internal doc_prompts/ so main agents cannot invoke kb-doc)")
        else:
            print("[WOULD REMOVE] skills/kanban-doc/SKILL.md (migrated to doc_prompts/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
