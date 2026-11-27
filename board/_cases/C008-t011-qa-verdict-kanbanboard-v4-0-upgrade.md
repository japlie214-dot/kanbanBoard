---
id: C008
title: "T011 QA verdict: KanbanBoard v4.0 upgrade"
kind: qa
author: kb-qa
created_at: "2026-11-27T05:39:30Z"
updated_at: "2026-11-27T05:39:30Z"
tickets:
  - "kanban-system/core/T011"
projects:
  - "kanban-system"
epics:
  - "kanban-system/core"
ticket_titles_json: "{\"kanban-system/core/T011\": \"Upgrade KanbanBoard to v4.0: V0.0.0 SemVer, disjoint clustering, living docs (kb-doc), sterilized CLI runner, and Web App menu nav\"}"
attachments: []
---
## Initial Post (kb-qa · 2026-11-27T05:39:30Z)
## Ponytail Diff
Reviewed v4.0 implementation across `kb_version.py`, `kb_doc_store.py`, `kb_doc_runner.py`, `doc_shared/*`, `resources/v4_nav.*`, `resources/board.html`, `viewer.py`, `mcp_server.py`, `package.py`, `plugin.json`, `.claude-plugin/plugin.json`, `scripts/wire_v4.py`, `skills/kanban/SKILL.md`, `skills/kanban-doc/SKILL.md`, `tests/test_qa_lock.py`, and `tests/test_v4_version_doc_and_runner.py`. All 3 prior P2 hardening items (`_validate_project` traversal guards in `kb_version.py` & `kb_doc_store.py`, unquoted `on*=` and dangerous URI stripping in `sanitize_tell_html`, and strict-CSP `doc_shared/starter-template.html`) are in place and tested.

## Testing Ladder
- Unit / Integration (`tests/test_v4_version_doc_and_runner.py`): 10 tests ran in 13.894s -> OK.
- Unit / Security (`tests/test_qa_lock.py`): 14 tests ran in 2.526s -> OK.
- Wiring idempotency (`scripts/wire_v4.py --dry-run`): exit 0 (`[OK]` on all 5 targets).
- Done signature check (`scripts/pre_commit_verify_done.py`): `verify-done: OK` (exit 0).
- E2E (`test_viewer_server_and_ui_payload_masterclass`): n/a in this run (per unchained command policy without `$env:KANBAN_TEST_AUTO_CONFIRM`; loopback HTTP routes and strict-CSP checks covered by `test_viewer_v4_routes_and_strict_csp_assets`).

## Positive + Pluto Witness
- Positive: `n - 1` accounting preserves signed `done` ticket files, Union-Find disjoint clustering & cluster-aware snooze (`>=7`, `+2`, larger-cluster takeover), sterilized `agy`/`codex` fallback, work-mode `version_nudge` + `kanban_project` bump/history, and 200 responses on `/doc-shared/*`, `/assets/v4_nav.*`, `/api/doc/show.js`.
- Pluto Negative: equal/downgrade/malformed SemVer rejected; `../escape` rejected in `validate_slug`, `doc_root`, and `bump_project_version`; `<script>`, quoted/unquoted `on*=`, and `javascript:` URIs stripped; open feedback preserved across 120d purge; `mode="qa"` omits `kanban_project` and `version_nudge`; CSRF-less `POST /api/doc/config` rejected with 403.

## Advisory Notes
- Pre-existing repo state (unrelated to T011): `kanban_board(view="lint")` reports missing `project.md` / `epic.md` under `board/_cases/`.

## Verdict: PASS
Full evidence recorded at `evidence/kanban-system/core/T011-qa.md`.
