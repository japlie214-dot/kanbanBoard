---
name: kanban
description: "Use when creating, claiming, updating, retiring, restoring, or verifying coding tasks on the central Kanban board."
---
# Kanban (Caveman)

Rules:
- Non-trivial work needs ticket first. Central board only; never create `board/` in app repo.
- Never self-approve `done` (only `kb-qa` or human via web app). Never edit `board/` or call `kb.py qa` directly.
- Never commit/push before ticket `done`.

Flow:
1. Check board: `kanban_board(view="overview", page=1, page_size=25)` (filter with `project`, `epic`, `status`, `q`; `include_retired=false` by default). Read `project.md`/`epic.md` via `kanban_doc` if unfamiliar.
2. Create: `kanban_ticket(action="create", project, epic, title, outcome, prove, plan)` — simple steps (1-2 for quick fixes; add `[after:]`/`[when:]`/`[parallel]` only if real fork/parallel exists).
3. Claim: `kanban_move(ref, status="in-progress", agent_id)` (auto-restores if retired).
4. Update: `kanban_update(ref, checked_nodes, node_proofs, skip_nodes?, files?)`.
5. Retire/Restore/Rehome: `kanban_ticket(action="retire", ref, reason)` moves non-done ticket back to `backlog` marked retired (auto hard-deletes after 120d). Use `action="restore"` to un-retire or `action="rehome", new_epic=...` to move epics.
6. Verify: run `## Prove` (positive + negative check), then `kanban_move(ref, status="verify", note)`.
7. QA: spawn `kb-qa` subagent (do NOT override `model`). Work on next ticket while QA runs.

Tools: `kanban_board`, `kanban_ticket`, `kanban_move`, `kanban_update`, `kanban_doc`, `kanban_view`.
