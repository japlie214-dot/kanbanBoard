---
id: C013
title: "QA Verdict PASS: T012 KanbanBoard v4.0.1 Upgrade"
kind: qa
author: kb-qa
created_at: "2026-11-27T07:56:20Z"
updated_at: "2026-11-27T07:56:20Z"
tickets:
  - "kanban-system/core/T012"
projects:
  - "kanban-system"
epics:
  - "kanban-system/core"
ticket_titles_json: "{\"kanban-system/core/T012\": \"Upgrade KanbanBoard to v4.0.1: global persistent kb-doc queue, doc_prompts, stack diagrams, TELL PDF export, rollback snapshots, and CSP UI polish\"}"
attachments: []
---
## Initial Post (kb-qa · 2026-11-27T07:56:20Z)
## Ponytail Diff
Inspected `git status -s`, `git diff`, and all v4.0.1 modules (`kb_doc_queue.py`, `kb_stack_diagram.py`, `kb_doc_export.py`, `kb_doc_v401.py`, `kb_doc_store.py`, `kb_doc_runner.py`, `doc_prompts/*`, `doc_shared/*`, `resources/board.js`, `resources/v4_nav.js`, `viewer.py`, `mcp_server.py`, `package.py`, `plugin.json`, `.claude-plugin/plugin.json`, `scripts/wire_v401.py`, `tests/test_v401_queue_export_and_diagram.py`, and deletion of `skills/kanban-doc/SKILL.md`).
- Global persistent single-worker `kb_doc_queue` enforces FIFO serialization via `_GLOBAL_LOCK`, coalesces TELL jobs, recovers crashed `running` jobs on startup, defers rate-limited errors (`429`/quota) with `120s/600s/1800s` backoff, and stops cleanly in `KanbanServer.server_close()`.
- Strict CSP (`style-src 'self'; script-src 'self'`) holds across `viewer.py` (`/api/doc/export/print.css` + `/api/doc/export/print-html`), `doc_shared/*`, `resources/board.js`, and `resources/v4_nav.js` (zero `style=`, zero inline handlers, zero `blob:` URLs).
- XSS defenses verified in `kb_stack_diagram.py` (`html.escape`, `SAFE_ID_RE`, cached SVG stripping of `<script>`/`<foreignObject>`/`on*`/`javascript:`/`vbscript:`) and `kb_doc_store.sanitize_tell_html`.
- `skills/kanban-doc/SKILL.md` is deleted (`D skills/kanban-doc/SKILL.md`) and replaced by internal `doc_prompts/*`.

## Testing Ladder
- Unit (`python -m unittest tests/test_v401_queue_export_and_diagram.py -v`): PASS (6/6 OK, 2.694s)
- Integration (`python -m unittest tests/test_v4_version_doc_and_runner.py -v`): PASS (10/10 OK, 4.184s)
- Integration (`python -m unittest tests/test_qa_lock.py -v`): PASS (14/14 OK, 0.400s)
- Idempotency (`python C:\Projects\kanbanBoard\scripts\wire_v401.py --dry-run`): PASS (all 3 targets `[OK] already up to date.`)
- Pre-commit Gate (`python C:\Projects\kanbanBoard\scripts\pre_commit_verify_done.py`): PASS (`verify-done: OK`)
- Component/Browser E2E: `n/a: headless browser render not executed in CLI audit; HTTP endpoint, CSP header/asset, and static JS CSP checks verified in unittest`

## Positive + Pluto Witness
- Positive: TELL coalescing (`V1.0.0` + `V1.1.0`), rate-limit deferral + post-backoff completion, `/health` `4.0.1`, `/api/doc/export/print-html` linking `print.css`, and `POST /api/doc/show/generate` returning `202`.
- Pluto Negative: invalid job mode / missing SHOW slug rejected (`ValueError`); empty diagram groups rejected (`ValueError`); `<script>` in title/`show_companion_html` escaped/stripped; `/api/doc/revert` without snapshots returns `400`; `skills/kanban-doc/SKILL.md` confirmed absent.

## Advisory Notes
- P2: `viewer.py` GET routes `/api/doc/export/*`, `/api/doc/manifest`, `/api/version/history` could map `ValueError` from invalid project slugs to HTTP `400` (matching `/api/doc/snapshots`).
- P2: `kb_doc_export.build_offline_html` embeds `<style>` for `download="..."` offline files; direct inline browser navigation under `style-src 'self'` uses `/api/doc/export/print-html` instead.
- P2: `kb_doc_queue.start_background_worker` could guard `_WORKER_THREAD`/`_WORKER_BOARD` mutation with a lifecycle lock.

## Verdict: PASS
Evidence written to `evidence/kanban-system/core/T012-qa.md`.
