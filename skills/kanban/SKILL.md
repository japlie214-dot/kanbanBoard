---
name: kanban
description: "Use when creating, claiming, updating, or verifying coding tasks on the central Kanban board."
---
# Kanban (Caveman)

Rules:
- Non-trivial work needs ticket first. Central board only; never create `board/` in app repo.
- Never self-approve `done` (only `kb-qa` or human via web app). Never edit `board/` or call `kb.py qa` directly.
- Never commit/push before ticket `done`.

Flow:
1. Check board: `kanban_board(view="overview")`. Read `project.md`/`epic.md` via `kanban_doc` if unfamiliar.
2. Create ticket: `kanban_ticket(action="create", project, epic, title, outcome, prove, plan)` — pass simple steps (1-2 for quick fixes; add `[after:]`/`[when:]`/`[parallel]` only if real fork/parallel exists). No `scaffold` template needed.
3. Claim: `kanban_move(ref, status="in-progress", agent_id)`.
4. Update: `kanban_update(ref, checked_nodes, node_proofs, skip_nodes?, files?)`.
5. Verify: run `## Prove` (positive + negative check), then `kanban_move(ref, status="verify", note)`.
6. QA: spawn `kb-qa` subagent (do NOT override `model`). Work on next ticket while QA runs.

Tools: `kanban_board`, `kanban_ticket`, `kanban_move`, `kanban_update`, `kanban_doc`, `kanban_view`.
