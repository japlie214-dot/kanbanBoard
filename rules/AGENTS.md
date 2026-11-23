# kanban-board Antigravity Plugin Rules

You are operating in a workspace that uses the **kanban-board** plugin for structured work tracking, quality assurance, multi-agent collaboration, and interactive visualization using the streamlined 7-tool Model Context Protocol (MCP) suite.

## Core Contract

Every piece of non-trivial work (feature, bug fix, refactor, investigation) MUST be tracked as a Kanban ticket before you start. **No ticket = no work.**

## Ticket Lifecycle

```
backlog ⇄ in-progress ⇄ verify → done
   ⇅          ⇅          ⇅
blocked    blocked    blocked
```

- **backlog**: Tickets not actively worked on yet.
- **in-progress**: Ticket actively owned and leased by an agent. Moving from `backlog` automatically claims the ticket with a 60-minute lease and requires a valid `## Plan (Todo Tree)` DAG.
- **verify**: Implementation finished, living documentation synchronized, physical git changes verified, unbroken DAG acceptance path completed, all execution proofs recorded in `## Execution Log`. Locked for `kb-qa`.
- **done**: Independent `kb-qa` subagent has certified the ticket after completing a 4-tier audit (DAG Process Audit, Tree diff, surrounding ecosystem blast-radius & living docs, and Horse vs. Zebra discriminator tests).
- **blocked**: Work paused due to an external impediment (requires note).

---

## Strict DAG Policy for Active Work

> [!IMPORTANT]
> Only tickets already in `done` are tolerated with legacy structures. Any active ticket in `backlog`, `in-progress`, `verify`, or `blocked` **must** adhere to the new DAG format (`[START]`, explicit dependencies, terminal acceptances, mandatory acceptances, execution proofs). Agents cannot claim or move tickets with non-compliant Todo Trees until they are upgraded via `kanban_ticket(action="edit", ...)` or updated to the new DAG specification.

---

## The Living Documentation & Charter Protocol (The 5 Pillars)

Documentation is a living architectural contract, not a static afterthought. Every agent must adhere to the 5 pillars:
1. **Pre-Flight Reading**: Before claiming or planning any ticket, read the project charter (`kanban_doc(action="read", project="...")`) and epic spec (`kanban_doc(action="read", project="...", epic="...")`). Never implement without context.
2. **Living Architecture Stewardship**: Keep `project.md` and `epic.md` synchronized with code reality:
   - Update `project.md` when introducing new runtime dependencies, environment variables, or build/deployment workflows.
   - Update `epic.md` when introducing new interfaces, public functions, CLI flags, database schemas, or communication protocols.
3. **Supplementary Technical Knowledge Base**: Agents are empowered and expected to create supplementary architectural docs beyond `project.md` and `epic.md` using `kanban_doc(action="write", project=..., epic=..., name="<topic>", content=...)` (e.g., `adr-<nnn>`, `api-specs`, `db-schema`, `benchmarks`, `troubleshooting`).
4. **Todo Tree Documentation Node**: Include a living documentation sync item in the `## Plan (Todo Tree)` DAG for any ticket modifying contracts or interfaces.
5. **QA Documentation Enforcement**: `kb-qa` will reject tickets during Tier 2 audit if interfaces, commands, or schemas were altered without updating `epic.md` or authoring supplementary documentation.

---

## The 5 Anti-Laziness Mechanical Gates

The state engine strictly enforces quality standards in code:
1. **The Non-Trivial Plan Gate (`backlog -> in-progress`)**:
   - `## Plan (Todo Tree)` must be an acyclic DAG with a `[START]` node, at least 2 checkpoints, every terminal leaf marked `[ACCEPTANCE:MANDATORY]` or `[ACCEPTANCE:OPTIONAL]`, and at least one `[ACCEPTANCE:MANDATORY]` node.
   - Rejects moving to `in-progress` if any `[ACCEPTANCE]` leaf is already checked `- [x]`.
2. **The "Zero Work" Git Gate (`in-progress -> verify`)**:
   - Checks `git status --porcelain`. Moving to `verify` is **hard-rejected** if git detects zero file changes.
3. **The Mandatory DAG & Process-Proof Gate (`in-progress -> verify`)**:
   - ALL active `[ACCEPTANCE:MANDATORY]` checkpoints and every active checkpoint from `[START]` to them must be checked (`- [x]`) AND backed by execution proof in `## Execution Log`. Optional branches must be fully completed or cleanly skipped (`- [-]`).
4. **The Real Prove Command Gate (`in-progress -> verify`)**:
   - Rejects trivial mock commands (`echo`, `true`, `exit 0`, placeholder hints). Must specify concrete test commands.
5. **The Ephemeral Proof-of-QA Gate (`kanban_qa(action='approve')`)**:
   - Requires substantive evidence file containing Process & Checkpoint Audit (citing all mandatory acceptance IDs), Diff Review, Living Architecture & Docs verification, Positive Tests, Negative Discriminator Tests, and `Verdict: PASS`. Ephemeral nonce is burned upon approval (or rejection via `kanban_qa(action='reject')`).

---

## The 7 Harmonized MCP Tools

1. **`kanban_board(view, project, epic, status)`**:
   Unified discovery, board initialization, listing, and health checks (`view="overview" | "init" | "list" | "lint"`).
2. **`kanban_ticket(action, ref, project, epic, title, outcome, scope, plan, prove, body)`**:
   Create, inspect, or edit tickets (`action="show" | "create" | "edit"`).
3. **`kanban_move(ref, status, note, agent_id, session_id, lease_minutes, force, reason)`**:
   Lifecycle and ownership engine with atomic lease claiming and force takeover logging.
4. **`kanban_update(ref, checked_nodes, node_proofs, skip_nodes, skip_reason, uncheck_nodes, files, notes, attach_file, attach_desc, detach_file)`**:
   In-flight DAG progress, execution proofs, branch decisions, and artifact logger (returns newly unblocked `ready_nodes`).
5. **`kanban_doc(action, project, epic, name, content)`**:
   Read, write, or list project charters, epic specifications, ADRs, and technical markdown documents (`name` optional; defaults to `"epic"` or `"project"`).
6. **`kanban_view(open_browser)`**:
   Launch or render the view-only web dashboard widget (`http://127.0.0.1:7890`).
7. **`kanban_qa(action, ref, qa_nonce, evidence_path, note)`**:
   RESTRICTED QA protocol for `kb-qa` (`action="start" | "approve" | "reject"`).

---

## Strict Prohibitions
1. **Never attempt to mark `done` yourself:** Only `kb-qa` can approve tickets to `done`.
2. **Never commit or push unless ticket is `done`:** Git commits are prohibited until certified.
3. **No hand-edits to YAML status:** Always use MCP tools.
4. **Never skip living documentation:** Update `epic.md`/`project.md` whenever interfaces, dependencies, or contracts change.
5. **Never bulk-check checkboxes without execution proofs:** Every completed checkpoint must have evidence in `## Execution Log`.
