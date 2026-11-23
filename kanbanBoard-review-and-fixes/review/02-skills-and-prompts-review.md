# 2. Skills & Agent Prompts Review

**Repository Audited:** [`japlie214-dot/kanbanBoard`](https://github.com/japlie214-dot/kanbanBoard)  
**Files Audited:**
- [`skills/kanban/SKILL.md`](https://github.com/japlie214-dot/kanbanBoard/blob/main/skills/kanban/SKILL.md)
- [`skills/kanban-qa/SKILL.md`](https://github.com/japlie214-dot/kanbanBoard/blob/main/skills/kanban-qa/SKILL.md)
- [`agents/kb-qa.md`](https://github.com/japlie214-dot/kanbanBoard/blob/main/agents/kb-qa.md)
- [`rules/AGENTS.md`](https://github.com/japlie214-dot/kanbanBoard/blob/main/rules/AGENTS.md) & [`CLAUDE.md`](https://github.com/japlie214-dot/kanbanBoard/blob/main/CLAUDE.md)
- `commands/kanban-{init,move,new,qa,status}.md`

---

## 1. Skill Inventory & Use Cases

There are **2 skills** under `skills/` (plus 1 agent definition under `agents/`, 2 rule files, and 5 slash commands under `commands/`):

| Skill / File | Name | Primary Use Case | Overall Grade |
|---|---|---|---|
| `skills/kanban/SKILL.md` | `kanban` | Guides primary coding agents through board discovery, pre-flight charter reading, ticket creation, lease claiming, Todo Tree progress tracking, living documentation stewardship, and submitting to `verify`. | **C+ (Broken Examples & Incomplete)** |
| `skills/kanban-qa/SKILL.md` | `kanban-qa` | Guides the independent `kb-qa` subagent through the 3-tier QA audit (minimal diff, blast-radius + living docs, Horse vs. Zebra discriminator tests) and nonce-gated approval to `done`. | **B- (Good Philosophy, Missing Process Audit & Drifted)** |
| `agents/kb-qa.md` *(companion)* | `kanban-qa` | Standalone agent persona prompt for `kb-qa`. | **C (Drifted from `skills/kanban-qa/SKILL.md`)** |
| `rules/AGENTS.md` & `CLAUDE.md` *(companions)* | Workspace rules | Global runtime contract for Antigravity and Claude Code agents. | **C+ (Contradicts `kb.py` & `mcp_server.py`)** |
| `commands/kanban-*.md` *(companions)* | Slash commands | User-triggered shortcuts (`/kanban-init`, `/kanban-new`, `/kanban-move`, `/kanban-qa`, `/kanban-status`). | **C- (Multiple API & Protocol Mismatches)** |

---

## 2. Detailed Critique: Are They Well Written?

### A. `skills/kanban/SKILL.md` — Verdict: **Broken API calls & incomplete workflow**
**What works well:**
- Clear 5-Pillar Living Documentation philosophy ("Read Before Plan", "Evolve as You Build", ADRs, doc sync node, QA doc gate).
- Clean table of the 7 MCP tools and a linear 6-step runbook.

**Defects, Inconsistencies & Incompleteness:**
1. **Broken `kanban_doc` examples (Runtime Crash):** Every `kanban_doc` example for `project.md` / `epic.md` omits `name`:
   ```python
   kanban_doc(action="read", project="myproj")
   kanban_doc(action="write", project="myproj", epic="core", content="...")
   ```
   Yet `mcp_server.py` marks `"required": ["action", "project", "name"]` and does `doc_name = args["name"]` — causing an immediate `KeyError: 'name'`!
2. **Platform-Locked Description:** Frontmatter says `"Unified Kanban board management for Antigravity agents"` even though the repo markets itself as `v2.0.0 Universal` (Antigravity + Claude Code).
3. **Missing Ticket Editing Step:** Step 2 says *"Fill in `## Outcome`, `## Scope`, `## Plan (Todo Tree)`, and `## Prove`"* — without explaining *how*! There is no MCP tool to edit ticket sections, leaving agents confused whether to raw-edit the markdown file (which risks violating `rules/AGENTS.md`'s "No hand-edits to YAML status").
4. **Incomplete Todo Tree Guidance:** Only shows a trivial nested list with decorative `[CHOSEN]` tags; does not document parallel lanes, `if/else` conditions, merges, mandatory vs. optional acceptances, or per-checkpoint execution proofs.
5. **Missing Failure/Rejection & Lease-Takeover Recovery:** Does not explain how the primary agent should respond when `kb-qa` rejects a ticket back to `in-progress`, how to handle `blocked` tickets, or when/how to use `force=True` takeover.

### B. `skills/kanban-qa/SKILL.md` — Verdict: **Strong QA mindset, but misses Process Verification and drifts from companions**
**What works well:**
- Memorable, high-signal engineering heuristics: *Ponytail philosophy* ("The best code is the code you never wrote"), *Surrounding Forest* blast-radius check, and *Horse vs. Zebra* positive + negative discriminator testing.
- Concrete evidence report template.

**Defects, Inconsistencies & Incompleteness:**
1. **Result-Only Verification (No Process Audit):** Checks `git diff`, callers, docs, and final `## Prove` commands, but **never checks whether the Todo Tree checkpoints from `START` to all mandatory acceptances were actually executed in order with real evidence**. An agent could skip intermediate design/migration/benchmark checkpoints, bulk-check them all at the end, and pass `kb-qa`.
2. **Duplicate & Drifted Copy in `agents/kb-qa.md`:** `agents/kb-qa.md` is a near-duplicate of `skills/kanban-qa/SKILL.md` that **omits the entire Living Documentation Audit** under Tier 2 and the Living Docs line in the evidence report template. Having two manually synced copies guarantees drift.
3. **Asymmetric Failure Path:** Pass calls `kanban_qa(action="approve", ...)`, while Fail falls back to `kanban_move(ref=..., status="in-progress", ...)` — no `kanban_qa(action="reject", ...)` and no FAIL evidence report requirement.
4. **Platform-Specific Subagent Snippet:** Hardcodes `invoke_subagent(TypeName="self", ...)` while `commands/kanban-qa.md` uses `Agent(subagent_type="kb-qa", ...)`. A universal skill should document the logical contract cleanly without conflicting tool signatures.

### C. Cross-File Inconsistencies (`rules/AGENTS.md`, `CLAUDE.md`, `commands/*.md` vs. `kb.py`)
1. **Gate 1 Spec Mismatch:** `rules/AGENTS.md` and `CLAUDE.md` claim Gate 1 requires *"at least 2 levels or 3 tasks"*, whereas `kb.py` actually enforces `len(nodes) < 2` (2 tasks, no depth check).
2. **Gate 5 Spec Mismatch:** `rules/AGENTS.md` and `CLAUDE.md` claim `api_qa_approve` verifies *"Living Architecture & Docs verification"*, whereas `kb.py` only checks `("Diff", "Positive Tests", "Negative Discriminator Tests", "PASS")`.
3. **Stale Tool Name in `kb.py`:** `api_move` error message tells agents to call `kanban_qa_approve` (v1 name) instead of `kanban_qa(action="approve", ...)`.
4. **`commands/kanban-qa.md` Drift:** Omits Tier 2 Living Docs audit, uses `evidence/<ref>-qa.md` instead of `evidence/<project>/<epic>/<tid>-qa.md`, and uses `Agent(subagent_type="kb-qa", ...)` instead of `invoke_subagent(...)`.
5. **`commands/kanban-move.md` & `commands/kanban-status.md` Gaps:** `kanban-move.md` omits `agent_id`; `kanban-status.md` omits `/kanban-init` / `kanban_board(view="init")`.

---

## 3. Fixes Included in `diffs/03-skills-agents-rules-sync.patch`

- Unified `skills/kanban/SKILL.md` with: universal description, valid `kanban_doc` calls (paired with optional `name` fix in `mcp_server.py`), new DAG Todo Tree syntax (parallel, `if/else`, merges, mandatory/optional acceptances, execution proofs), `kanban_ticket(action="edit")` workflow, and QA-rejection recovery.
- Upgraded `skills/kanban-qa/SKILL.md` and synchronized `agents/kb-qa.md` with **Tier 0: Process & Checkpoint Execution Audit** (verifying every checkpoint from `START` to all mandatory acceptances was executed in order with proof), unified Living Docs audit, and `kanban_qa(action="reject", ...)` for symmetric fail handling.
- Synchronized `rules/AGENTS.md`, `CLAUDE.md`, and `wiki/Executable-Todo-Tree.md` so documentation, gates, and code match 1-to-1.
