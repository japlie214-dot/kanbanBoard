# 3. MCP Tools Arsenal UX & Ergonomics Review

**File Audited:** [`mcp_server.py`](https://github.com/japlie214-dot/kanbanBoard/blob/main/mcp_server.py) (500 lines, 7 tools)

---

## Executive Verdict

Consolidating the MCP surface down to **7 tools** is a smart architectural choice for LLM token budgets and tool-selection accuracy. However, the **internal UX of those 7 tools has several rough edges, broken contracts, and missing operations** that will cause agents to fail on first attempt, fall back to raw file editing, or silently lose state.

---

## Tool-by-Tool UX Scorecard

| # | Tool | UX Grade | Strengths | Key UX & Correctness Issues |
|---|---|---|---|---|
| 1 | `kanban_board` | **B+** | Clean single entry point for `overview`, `init`, `list`, `lint`. | Inconsistent output format: `overview`/`list` return raw JSON while `lint` returns emoji plain text and `init` returns a sentence. |
| 2 | `kanban_ticket` | **C** | Auto-ID assignment when `project` + `epic` given is handy. | **Implicit mode overloading**: passing `title` creates, omitting `title` reads — fragile and unintuitive. **No `edit` action**: agents cannot populate `Outcome`, `Scope`, `Plan (Todo Tree)`, or `Prove` via MCP, forcing raw filesystem edits right after creation! |
| 3 | `kanban_move` | **C+** | Atomic claim + 60m lease on `in-progress` is great UX. | **Dead parameter bug**: `reason` is declared in `inputSchema` for `force=True` takeover, but `handle_tool_call` never reads or passes it! Also returns stale `kanban_qa_approve` error text from `kb.py`. |
| 4 | `kanban_update` | **C-** | Auto-renewing the 60m lease on progress updates is great. | **Kitchen-sink overload** (nodes + files + notes + attach + detach in one tool). **No `proof` per node** (cannot verify process execution). **No `skip_nodes` or `uncheck_nodes`** (cannot record `if/else` or optional branch decisions, or fix a typo). Silent no-op when a node ID doesn't match. |
| 5 | `kanban_doc` | **D+** | Supports arbitrary ADRs/specs beyond `project.md`/`epic.md`. | **Broken ergonomics**: `name` is `"required"` even when reading/writing the default `project.md` or `epic.md`, causing every example in `SKILL.md` and `AGENTS.md` to crash with `KeyError: 'name'`. No `list` action to discover existing docs in a project/epic. |
| 6 | `kanban_view` | **C+** | Nice MCP UI resource (`ui://kanban/board`) + browser fallback. | **Duplicate server bug**: every call with `open_browser=True` spawns a new daemon thread calling `viewer.run_server(..., port=7890)` with no singleton/running guard. |
| 7 | `kanban_qa` | **C+** | Clean nonce-based anti-cheat handshake (`start` -> `approve`). | **Asymmetric API**: has `start` and `approve`, but **no `reject` action**! On failure, `kb-qa` must switch tools to `kanban_move(status="in-progress")` and loses structured rejection/evidence logging. `start` returns JSON while `approve` returns prose text. |

---

## Cross-Cutting UX Problems

1. **Missing Edit Path Breaks the "MCP-Only" Rule:**
   `kanban_ticket` creates a stub with placeholders, `kanban_move(status="in-progress")` rejects placeholders, yet **no MCP tool exists to edit the ticket body**. Adding an explicit `action="edit"` (with optional `outcome`, `scope`, `plan`, `prove`, or `body`) to `kanban_ticket` closes the loop completely.
2. **Implicit vs. Explicit Dispatch:**
   - `kanban_board` uses `view`, `kanban_doc` and `kanban_qa` use `action`, and `kanban_ticket` uses implicit presence of `title`. Standardizing on explicit `action` enums makes LLM tool calling significantly more reliable.
3. **Schema-to-Runtime Drift:**
   - `kanban_move.reason` is in the JSON schema but silently dropped in Python.
   - `kanban_doc.name` is required in the JSON schema but omitted in every skill/rule/command doc.
4. **No DAG / Process Support in `kanban_update`:**
   To support your DAG workflow and process verification, `kanban_update` needs:
   - `complete_nodes` (or `checked_nodes`) with structured `node_proofs: {node_id: "command/artifact proof"}`
   - `skip_nodes` with `skip_reason` (to mark untaken `if/else` or optional branches as `- [-]`)
   - `uncheck_nodes` (for rollback/correction)
   - Clear error reporting when a node ID does not exist or its `after:` prerequisites are not yet completed, plus returning the list of **newly unblocked / ready nodes** so parallel agents know what can run next!
5. **No Output Format Consistency:**
   Some tools return pure JSON, some return Markdown/plain text, and `kanban_ticket(show)` returns a mix of prose + JSON frontmatter + raw Markdown. Returning consistent structured text or JSON with clear next-step hints improves agent reliability.

---

## Fixes Included in `diffs/02-mcp-server-ux-fixes.patch`

1. **`kanban_doc`**: Make `name` optional (auto-defaults to `"epic"` when `epic` is provided, else `"project"`), and add `action="list"` to enumerate docs.
2. **`kanban_ticket`**: Add explicit `action` (`"show" | "create" | "edit"`, keeping backward-compatible inference when `action` is omitted) so agents can populate `Outcome`, `Scope`, `Plan (Todo Tree)`, and `Prove` without raw file hacks.
3. **`kanban_move`**: Wire `reason` into `note` / handover log on `force=True` takeovers, and fix the stale `kanban_qa_approve` reference.
4. **`kanban_update`**: Support `node_proofs` (process execution evidence per checkpoint), `skip_nodes` + `skip_reason` (for `if/else` and optional branches), `uncheck_nodes`, strict dependency-order enforcement, and return `ready_nodes` (next unblocked DAG checkpoints).
5. **`kanban_qa`**: Add `action="reject"` (burns nonce, records rejection reason + optional FAIL evidence path, moves ticket back to `in-progress`) for symmetric QA ergonomics.
6. **`kanban_view`**: Guard `viewer.run_server` behind a module-level `_VIEWER_STARTED` flag so repeated calls don't spawn duplicate server threads.
