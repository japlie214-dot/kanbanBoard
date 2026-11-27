#!/usr/bin/env python3
"""scripts/wire_v4.py — Idempotently wires KanbanBoard v4.0 into viewer.py,
mcp_server.py, resources/board.html, skills/kanban/SKILL.md, and .claude-plugin/plugin.json.

Changes applied:
  1. viewer.py:
     - Imports kb_version, kb_doc_store, kb_doc_runner.
     - Serves /doc-shared/* from doc_shared/ and /assets/v4_nav.{css,js} via self._send / self._serve_file.
     - Adds GET endpoints: /api/version/history, /api/doc/config, /api/doc/manifest,
       /api/doc/section, /api/doc/overrides.css, /api/doc/feedback.
     - Adds Origin + X-Kanban-CSRF protected POST endpoints: /api/version/bump (stamps n-1 tickets
       + queues async kb-doc TELL), /api/doc/config (Boss global/project config), /api/doc/feedback,
       /api/doc/show/generate (Boss on-demand SHOW).
     - Bumps viewer version banner to 4.0.0.
  2. resources/board.html:
     - Loads /doc-shared/base.css, /assets/v4_nav.css, /doc-shared/cinema-engine.js,
       /doc-shared/shell.js, and /assets/v4_nav.js.
  3. mcp_server.py:
     - Imports kb_version, kb_doc_store, kb_doc_runner.
  4. skills/kanban/SKILL.md & .claude-plugin/plugin.json:
     - Adds concise v4.0 SemVer & version_nudge guidance and bumps plugin version to 4.0.0.
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
    if "import kb_version" not in out:
        if "import kb_cases\n" in out:
            out = out.replace(
                "import kb_cases\n",
                "import kb_cases\nimport kb_version\nimport kb_doc_store\nimport kb_doc_runner\n",
                1,
            )
        elif "import kb_crud\n" in out:
            out = out.replace(
                "import kb_crud\n",
                "import kb_crud\nimport kb_version\nimport kb_doc_store\nimport kb_doc_runner\n",
                1,
            )

    out = out.replace('"version": "3.0.0"', '"version": "4.0.0"')
    out = out.replace('"version": "2.6.0"', '"version": "4.0.0"')
    out = out.replace("KanbanViewer/3.0", "KanbanViewer/4.0")
    out = out.replace("KanbanViewer/2.6", "KanbanViewer/4.0")
    out = out.replace("Kanban Board Viewer v3.0", "Kanban Board Viewer v4.0")

    if 'dirs[:] = [d for d in dirs if not d.startswith(".")]' in out:
        out = out.replace(
            'dirs[:] = [d for d in dirs if not d.startswith(".")]',
            'dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("_doc_sandbox", "_doc_home")]',
            1,
        )

    # Add v4 GET routes before `if path == "/api/ticket":`
    if 'path == "/api/version/history"' not in out and 'if path == "/api/ticket":' in out:
        v4_get_routes = (
            'if path.startswith("/doc-shared/"):\n'
            '            fname = path[len("/doc-shared/"):].strip("/")\n'
            '            shared_root = (REPO_ROOT / "doc_shared").resolve()\n'
            '            shared_file = (shared_root / fname).resolve()\n'
            '            if shared_root not in shared_file.parents or not shared_file.is_file():\n'
            '                return self._json(404, {"ok": False, "error": "shared asset not found"}, head)\n'
            '            ctype = "text/css; charset=utf-8" if fname.endswith(".css") else ("application/javascript; charset=utf-8" if fname.endswith(".js") else "text/html; charset=utf-8")\n'
            '            return self._send(200, shared_file.read_bytes(), ctype, head)\n\n'
            '        if path in ("/assets/v4_nav.css", "/assets/v4_nav.js"):\n'
            '            fname = path[len("/assets/"):]\n'
            '            ctype = "text/css; charset=utf-8" if fname.endswith(".css") else "application/javascript; charset=utf-8"\n'
            '            return self._serve_file(REPO_ROOT / "resources" / fname, ctype, head)\n\n'
            '        if path == "/api/version/history":\n'
            '            proj = (qs.get("project") or [""])[0].strip()\n'
            '            if not proj:\n'
            '                return self._json(400, {"ok": False, "error": "missing project"}, head)\n'
            '            cfg = kb_doc_store.load_effective_config(self.server.board, proj)\n'
            '            return self._json(200, kb_version.get_version_history(self.server.board, proj, config=cfg), head)\n\n'
            '        if path == "/api/doc/config":\n'
            '            proj = (qs.get("project") or [""])[0].strip() or None\n'
            '            return self._json(200, {\n'
            '                "ok": True,\n'
            '                "global": kb_doc_store.load_global_config(self.server.board),\n'
            '                "effective": kb_doc_store.load_effective_config(self.server.board, proj),\n'
            '                "runs": kb_doc_store.list_runs(self.server.board, proj) if proj else [],\n'
            '            }, head)\n\n'
            '        if path == "/api/doc/manifest":\n'
            '            proj = (qs.get("project") or [""])[0].strip()\n'
            '            if not proj:\n'
            '                return self._json(400, {"ok": False, "error": "missing project"}, head)\n'
            '            return self._json(200, kb_doc_store.load_manifest(self.server.board, proj), head)\n\n'
            '        if path == "/api/doc/section":\n'
            '            proj = (qs.get("project") or [""])[0].strip()\n'
            '            slug = (qs.get("slug") or [""])[0].strip()\n'
            '            try:\n'
            '                return self._json(200, kb_doc_store.read_section(self.server.board, proj, slug), head)\n'
            '            except (FileNotFoundError, ValueError) as e:\n'
            '                return self._json(404, {"ok": False, "error": str(e)}, head)\n\n'
            '        if path == "/api/doc/show.js":\n'
            '            proj = (qs.get("project") or [""])[0].strip()\n'
            '            slug = (qs.get("slug") or [""])[0].strip()\n'
            '            try:\n'
            '                sec = kb_doc_store.read_section(self.server.board, proj, slug)\n'
            '                if not sec.get("has_show") or not sec.get("show_js"):\n'
            '                    return self._json(404, {"ok": False, "error": "SHOW module not generated"}, head)\n'
            '                return self._send(200, sec["show_js"].encode("utf-8"), "application/javascript; charset=utf-8", head)\n'
            '            except (FileNotFoundError, ValueError) as e:\n'
            '                return self._json(404, {"ok": False, "error": str(e)}, head)\n\n'
            '        if path == "/api/doc/overrides.css":\n'
            '            proj = (qs.get("project") or [""])[0].strip()\n'
            '            css = kb_doc_store.read_overrides_css(self.server.board, proj) if proj else ""\n'
            '            return self._send(200, css.encode("utf-8"), "text/css; charset=utf-8", head)\n\n'
            '        if path == "/api/doc/feedback":\n'
            '            proj = (qs.get("project") or [""])[0].strip()\n'
            '            if not proj:\n'
            '                return self._json(400, {"ok": False, "error": "missing project"}, head)\n'
            '            cfg = kb_doc_store.load_effective_config(self.server.board, proj)\n'
            '            kb_doc_store.purge_expired_feedback(self.server.board, proj, int(cfg.get("feedback_retention_days", 120)))\n'
            '            return self._json(200, {"ok": True, "feedback": kb_doc_store.list_feedback(self.server.board, proj)}, head)\n\n'
            '        if path == "/api/ticket":'
        )
        out = out.replace('if path == "/api/ticket":', v4_get_routes, 1)

    # Add v4 Origin + X-Kanban-CSRF protected POST routes right before `return self._deny()` in do_POST
    if 'path == "/api/version/bump"' not in out and '        return self._deny()\n' in out:
        v4_post_routes = (
            '        if path in ("/api/version/bump", "/api/doc/config", "/api/doc/feedback", "/api/doc/show/generate"):\n'
            '            ctype = (self.headers.get("Content-Type") or "").lower()\n'
            '            if not ctype.startswith("application/json"):\n'
            '                return self._json(415, {"ok": False, "error": "Content-Type must be application/json"}, False)\n'
            '            port = self.server.server_address[1]\n'
            '            origin = (self.headers.get("Origin") or "").strip()\n'
            '            if origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:\n'
            '                return self._json(403, {"ok": False, "error": "forbidden: invalid Origin header"}, False)\n'
            '            token = (self.headers.get("X-Kanban-CSRF") or "").strip()\n'
            '            if not token or not hmac.compare_digest(token, self.server.csrf_token):\n'
            '                return self._json(403, {"ok": False, "error": "forbidden: invalid or missing CSRF token"}, False)\n'
            '            try:\n'
            '                length = int(self.headers.get("Content-Length", 0))\n'
            '                payload = json.loads(self.rfile.read(length).decode("utf-8"))\n'
            '                if path == "/api/version/bump":\n'
            '                    proj = str(payload.get("project") or "").strip()\n'
            '                    ver = str(payload.get("version") or "").strip()\n'
            '                    by = str(payload.get("bumped_by") or "Boss").strip()\n'
            '                    note = str(payload.get("note") or "").strip()\n'
            '                    res = kb_version.bump_project_version(self.server.board, proj, ver, bumped_by=by, note=note)\n'
            '                    cfg = kb_doc_store.load_effective_config(self.server.board, proj)\n'
            '                    if cfg.get("auto_tell_on_bump", True):\n'
            '                        threading.Thread(\n'
            '                            target=kb_doc_runner.run_tell_update,\n'
            '                            args=(self.server.board, proj, res["new_version"], res["shipped_tickets"]),\n'
            '                            daemon=True,\n'
            '                        ).start()\n'
            '                    return self._json(200, res, False)\n'
            '                if path == "/api/doc/config":\n'
            '                    scope = str(payload.get("scope") or "global").strip().lower()\n'
            '                    patch = payload.get("config") or {}\n'
            '                    if scope == "project" and payload.get("project"):\n'
            '                        saved = kb_doc_store.save_project_config(self.server.board, str(payload["project"]), patch)\n'
            '                    else:\n'
            '                        saved = kb_doc_store.save_global_config(self.server.board, patch)\n'
            '                    return self._json(200, {"ok": True, "config": saved}, False)\n'
            '                if path == "/api/doc/feedback":\n'
            '                    fb = kb_doc_store.add_feedback(\n'
            '                        self.server.board,\n'
            '                        str(payload.get("project") or "").strip(),\n'
            '                        str(payload.get("text") or ""),\n'
            '                        section=str(payload.get("section") or "global"),\n'
            '                        author=str(payload.get("author") or "Boss"),\n'
            '                    )\n'
            '                    return self._json(200, {"ok": True, "feedback": fb}, False)\n'
            '                if path == "/api/doc/show/generate":\n'
            '                    res = kb_doc_runner.run_show_generate(\n'
            '                        self.server.board,\n'
            '                        str(payload.get("project") or "").strip(),\n'
            '                        str(payload.get("slug") or "").strip(),\n'
            '                    )\n'
            '                    return self._json(200 if res.get("ok") else 500, res, False)\n'
            '            except (ValueError, FileNotFoundError) as e:\n'
            '                return self._json(400, {"ok": False, "error": str(e)}, False)\n'
            '            except Exception as e:\n'
            '                return self._json(500, {"ok": False, "error": f"server error: {e}"}, False)\n\n'
            '        return self._deny()\n'
        )
        out = out.replace('        return self._deny()\n', v4_post_routes, 1)

    return out


def patch_board_html(src: str) -> str:
    out = src
    if "/assets/v4_nav.css" not in out and '<link rel="stylesheet" href="/assets/board.css" />' in out:
        out = out.replace(
            '<link rel="stylesheet" href="/assets/board.css" />',
            '<link rel="stylesheet" href="/assets/board.css" />\n  <link rel="stylesheet" href="/doc-shared/base.css" />\n  <link rel="stylesheet" href="/assets/v4_nav.css" />',
            1,
        )
    if "/assets/v4_nav.js" not in out and '<script src="/assets/board.js" defer></script>' in out:
        out = out.replace(
            '<script src="/assets/board.js" defer></script>',
            '<script src="/assets/board.js" defer></script>\n  <script src="/doc-shared/cinema-engine.js" defer></script>\n  <script src="/doc-shared/shell.js" defer></script>\n  <script src="/assets/v4_nav.js" defer></script>',
            1,
        )
    return out


def patch_mcp_server(src: str) -> str:
    out = src
    if "import kb_version" not in out and "import kb\n" in out:
        out = out.replace(
            "import kb\n",
            "import kb\nimport kb_version\nimport kb_doc_store\nimport kb_doc_runner\n",
            1,
        )
    return out


def patch_kanban_skill(src: str) -> str:
    out = src
    if "bump_version" not in out:
        out = out.rstrip() + (
            "\n\n## Project Versioning (`V0.0.0`, `n - 1` Rule)\n"
            "- Tickets certified `done` while on `V2.0.0` belong to the next version (`V_next`).\n"
            "- When `kanban_board` surfaces a `version_nudge` (or after finishing a feature), decide whether to bump via `kanban_project(action=\"bump_version\", project, version=\"V...\")` (any strictly greater SemVer triggers `kb-doc` TELL automatically).\n"
            "- Inspect past releases and pending clusters via `kanban_project(action=\"version_history\", project)`.\n"
        )
    return out


def patch_plugin_json(src: str) -> str:
    return re.sub(r'"version"\s*:\s*"3\.\d+\.\d+"', '"version": "4.0.0"', src, count=1)


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
    parser = argparse.ArgumentParser(description="Wire KanbanBoard v4.0 upgrades")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    targets = [
        (ROOT / "viewer.py", patch_viewer),
        (ROOT / "resources" / "board.html", patch_board_html),
        (ROOT / "mcp_server.py", patch_mcp_server),
        (ROOT / "skills" / "kanban" / "SKILL.md", patch_kanban_skill),
        (ROOT / ".claude-plugin" / "plugin.json", patch_plugin_json),
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
