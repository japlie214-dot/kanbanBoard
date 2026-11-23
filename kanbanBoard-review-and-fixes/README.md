# kanbanBoard Review & Fixes Package

This archive contains a complete technical audit of [`japlie214-dot/kanbanBoard`](https://github.com/japlie214-dot/kanbanBoard) against your workflow drawing and requirements, along with unified code diffs ready to apply.

## Contents

### 1. Review & Judgement Reports (`review/`)
- `review/01-todo-tree-dag-review.md` — Gap analysis of the current indentation-tree Todo Tree vs. your A/B/C/D/E DAG drawing (parallel lanes, `if/else` forks, cross-branch merges, mandatory vs. optional acceptances, start/end invariants, and process+result QA).
- `review/02-skills-and-prompts-review.md` — Inventory and quality judgement of all skills (`skills/kanban/SKILL.md`, `skills/kanban-qa/SKILL.md`) and companion agent/rule/command files (`agents/kb-qa.md`, `rules/AGENTS.md`, `CLAUDE.md`, `commands/*.md`), cataloging every bug and cross-file drift.
- `review/03-mcp-tools-ux-review.md` — Tool-by-tool UX and ergonomics audit of the 7 MCP tools in `mcp_server.py`, highlighting schema/runtime crashes, dead parameters, missing edit/reject workflows, and duplicate server bugs.

### 2. Unified Code Diffs (`diffs/`)
- `diffs/01-kb-dag-and-process-qa.patch` — Core `kb.py` upgrades: true DAG parser & validator, start/end/cycle/mandatory/optional/`if-else` enforcement, dependency-ordered `api_checkpoint` with `## Execution Log` process proofs, `api_ticket_edit`, `api_doc` default `name` + `list`, `api_qa_reject`, and Gate 5 process-audit verification.
- `diffs/02-mcp-server-ux-fixes.patch` — `mcp_server.py` UX fixes: `kanban_ticket` `edit` action, `kanban_doc` optional `name` + `list`, `kanban_move` `reason` wiring, `kanban_update` `node_proofs`/`skip_nodes`/`uncheck_nodes`/`ready_nodes`, `kanban_qa` `reject` action, and `kanban_view` singleton guard.
- `diffs/03-skills-agents-rules-sync.patch` — Synchronizes `skills/kanban/SKILL.md`, `skills/kanban-qa/SKILL.md`, `agents/kb-qa.md`, `rules/AGENTS.md`, `CLAUDE.md`, and `wiki/Executable-Todo-Tree.md` with the new DAG Todo Tree, Tier 0 Process Audit, and fixed MCP schemas.
- `diffs/04-tests-dag-and-mcp.patch` — Adds comprehensive unit tests to `tests/test_kanban.py` covering the exact A/B/C/D/E drawing topology, process-proof enforcement, `kb-qa` process audit, and MCP UX fixes.

### 3. Worked Example (`examples/`)
- `examples/drawing-abcde-ticket.md` — Complete ticket markdown encoding your exact A/B/C/D/E drawing in the new Todo Tree DAG format.

## Applying the Patches

From the root of your `kanbanBoard` clone:
```bash
git apply --check diffs/01-kb-dag-and-process-qa.patch
git apply diffs/01-kb-dag-and-process-qa.patch
git apply diffs/02-mcp-server-ux-fixes.patch
git apply diffs/03-skills-agents-rules-sync.patch
git apply diffs/04-tests-dag-and-mcp.patch
python3 -m unittest tests/test_kanban.py -v
```
