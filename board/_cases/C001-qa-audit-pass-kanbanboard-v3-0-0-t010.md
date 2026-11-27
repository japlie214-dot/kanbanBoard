---
id: C001
title: "QA Audit PASS: KanbanBoard v3.0.0 (T010)"
kind: qa
author: kb-qa
created_at: "2026-11-26T09:00:31Z"
updated_at: "2026-11-26T09:00:31Z"
tickets:
  - "kanban-system/core/T010"
projects:
  - "kanban-system"
epics:
  - "kanban-system/core"
ticket_titles_json: "{\"kanban-system/core/T010\": \"Upgrade KanbanBoard to v3.0: build status, Cases, history snapshots, repo ID, and vanilla skills\"}"
attachments:
  - "_cases/attachments/C001/T010-qa.md"
---
## Initial Post (kb-qa · 2026-11-26T09:00:31Z)
## Ponytail Diff
Verified v3.0.0 deliverables across `kb.py`, `kb_cases.py`, `kb_history.py`, `kb_repo_id.py`, `mcp_server.py`, `viewer.py`, `resources/board.js`, `resources/board.css`, `package.py`, `scripts/install_qa_lock.py`, `scripts/migrate_in_progress_to_build.py`, `scripts/wire_v3.py`, `.claude-plugin/plugin.json`, `CLAUDE.md`, `rules/AGENTS.md`, `skills/kanban/SKILL.md` + `DAG-SYNTAX.md`, removal of `skills/kanban-qa/SKILL.md`, and `tests/test_v3_cases_history_and_build.py`.

## Testing Ladder
- **Unit**: `python -m unittest tests.test_v3_cases_history_and_build tests.test_qa_lock tests.test_v27_qa_otp -v` -> 28/28 PASS (7.260s); 9/9 non-modal tests in `tests/test_kanban.py` PASS (`test_viewer_server_and_ui_payload_masterclass` waited on OS `MessageBoxW` without `KANBAN_TEST_AUTO_CONFIRM=1`).
- **Integration**: `kanban_board(view="lint")` -> `Lint: OK`; `kanban_board(view="list", status="in-progress")` -> 5 `build` tickets; `kanban_case(action="list")` -> OK.
- **Component**: Covered by MCP `kanban_case` roundtrip and dual-mode MCP tests.
- **E2E**: `n/a` (headless subagent; static assets inspected).

## Positive + Pluto Witness
- Positive: `in-progress` -> `build` alias & migration preserving `done` HMAC signatures, cross-project Cases + attachments + `[DELETED]` tombstones + 180d archival, SHA-256 deduplicated `.history/*.jsonl` snapshots, `kb_repo_id` git root commit matching, 8-tool `WORK_TOOL_NAMES` / 4-tool `QA_TOOL_NAMES`.
- Pluto Witness: `kb_cases` rejects 0 and >100 tickets (`ValueError`); `api_qa_reject` unchecks `[ACCEPTANCE:MANDATORY]` leaves (`- [ ] A2`) and logs `verify -> build`; `kanban_qa` blocks missing/forged `qa_passkey` and `qa` mode blocks write actions.

## Advisory Notes (P2)
- `board/kanban-system/core/epic.md`, `kb.py` module docstring, and `viewer.py` module docstring still mention v2.x wording (`7 harmonized MCP tools` / `in-progress` / `v2.5`).
- `scripts/wire_v3.py` `patch_kb_py` performs a one-time `.replace('"in-progress"', '"build"')` which would match the alias inside `normalize_status` if re-run.

**Verdict: PASS**

### Attachments
- `_cases/attachments/C001/T010-qa.md`
