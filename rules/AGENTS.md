# kanban-board Antigravity Plugin Rules

You are operating in a workspace that uses the **kanban-board** plugin for structured work tracking, quality assurance, multi-agent collaboration, and interactive visualization using the streamlined 7-tool Model Context Protocol (MCP) suite.

## Core Contract

Every piece of non-trivial work (feature, bug fix, refactor, investigation) MUST be tracked as a Kanban ticket before you start. **No ticket = no work.**

### The Single Centralized Board Invariant
- **Strictly Centralized**: All projects (`coom`, `deckanim`, `kanban-system`, `memberberries`, `nightwatch`, `snowball`, etc.) are tracked exclusively in the **Central Kanban Board** (`C:\Projects\kanbanBoard\board` or `~/.kanban/board`).
- **Zero Repo Pollution**: Application repositories (e.g. `C:\Projects\etoroNightwatch`, `C:\Projects\coom`) must NEVER contain a `board/` directory. If you see an untracked `board/` in `git status` of an application repo, it is an error—do NOT commit it.
- **Universal Multi-Project Discovery**: The MCP tools automatically resolve to the centralized board regardless of what repository you are editing. Specify `project="<slug>"` (e.g. `project="nightwatch"`) to target the correct project container in the central board.

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
1. **Never create or commit a `board/` folder in application repositories:** The board is strictly centralized (`C:\Projects\kanbanBoard\board` / `~/.kanban/board`). Application repositories must stay completely clean.
2. **Never attempt to mark `done` yourself:** Only independent `kb-qa` can approve tickets to `done`. In Antigravity / Swarm, author agents must invoke a separate subagent (`invoke_subagent` with clean context) for QA verification rather than self-certifying in the same conversation.
3. **Never commit or push code unless ticket is certified `done`:** Git commits are prohibited until certified by `kb-qa`.
4. **No hand-edits to YAML status:** Always use MCP tools (`kanban_move`, `kanban_qa`).
5. **Never skip living documentation:** Update `epic.md`/`project.md` whenever interfaces, dependencies, or contracts change.
6. **Never bulk-check checkboxes without execution proofs:** Every completed checkpoint must have substantive evidence in `## Execution Log`.

---

## Agile DAG Planning & Parallel Execution Rules
1. **Never Default to Fragile Linear Waterfall Plans**: Non-trivial tickets (`in-progress`) must account for real-world uncertainty by incorporating at least one contingency branch (`[when:if/else]`), parallel lane (`[parallel]`), or fallback join (`[after:A|B]`).
2. **Instant Scaffolding**: Never write complex DAG syntax manually from scratch. Use `kanban_ticket(action="scaffold", pattern="agile")` or specify `pattern="agile|feature|spike|refactor"` during creation.
3. **Behavior on `[parallel]` Lanes**:
   - In Antigravity / Swarm: Coordinators may delegate unblocked parallel lanes (`ready_nodes`) to subagents via `invoke_subagent`.
   - In Standalone CLI (Claude Code / Codex): The agent must batch independent tool calls and non-blockingly switch between parallel lanes without retreating.
4. **Dynamic In-Flight Pivoting**: When an environmental probe or condition test fails, do not retreat or re-plan from scratch. Skip the untaken branch cleanly via `kanban_update(skip_nodes=[...], skip_reason="...")` and proceed to the fallback branch.
