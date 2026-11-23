---
name: kanban
description: Universal Kanban board management for AI coding agents (Antigravity, Claude Code, Codex). Unified discovery, atomic move-and-claim, true DAG Todo Tree execution with process proofs, safe attachments, and living architectural documentation.
---

# Kanban Board Skill

This skill guides agents on interacting with the local file-backed Kanban board using the streamlined 7-tool MCP suite.

## The 7 Harmonized Tools

| Tool | Core Capability | Typical Usage |
|---|---|---|
| `kanban_board` | Discover, init, list, or lint | `kanban_board(view="overview")` or `kanban_board(view="init", project="myproj")` |
| `kanban_ticket` | Create, inspect, or edit ticket sections | `kanban_ticket(action="create", project="web", epic="auth", title="OAuth")` or `kanban_ticket(action="edit", ref="web/auth/T001", plan="...")` |
| `kanban_move` | Move status & claim lease (supports `force` + `reason`) | `kanban_move(ref="web/auth/T001", status="in-progress", agent_id="agent-1")` |
| `kanban_update` | Complete DAG checkpoints with proofs, skip branches, log files/notes, attach | `kanban_update(ref="web/auth/T001", checked_nodes=["A1"], node_proofs={"A1": "pytest -> pass"})` |
| `kanban_doc` | Read, write, or list charters, epics & custom specs (`name` optional) | `kanban_doc(action="read", project="web", epic="auth")` or `kanban_doc(action="list", project="web")` |
| `kanban_view` | Open live web dashboard | `kanban_view()` |
| `kanban_qa` | Independent QA audit (kb-qa only: `start`, `approve`, `reject`) | `kanban_qa(action="start", ref="...")` |

---

## Todo Tree DAG Rules (Strict Process & Graph Contract)

Every ticket's `## Plan (Todo Tree)` is a true **Directed Acyclic Graph (DAG)** with explicit checkpoints:
- **Start & End Invariant**: Must begin at `[START]`; every terminal leaf MUST be `[ACCEPTANCE:MANDATORY]` or `[ACCEPTANCE:OPTIONAL]`.
- **Parallel Lanes**: Mark independent concurrent branches with `[lane:D] [after:A1] [parallel]`.
- **Conditional `if/else` Branches**: Use `[when:if(cond):fork1]` and `[when:else(cond):fork1]`. Mark the untaken branch skipped via `skip_nodes` + `skip_reason` (`- [-]`).
- **Cross-Branch Merges**: Use `[after:A2,B3?]` (optional/conditional merge) or `[after:A4,B5|C5]` (XOR merge) or `[after:A2,B3]` (AND join).
- **Execution Proof Required**: Check off nodes in dependency order via `kanban_update(..., checked_nodes=[...], node_proofs={...})`. Every completed checkpoint is logged in `## Execution Log` and audited by `kb-qa`.
- **Mandatory vs. Optional**: ALL active `[ACCEPTANCE:MANDATORY]` paths from `[START]` must be completed and proven before `verify`. `[ACCEPTANCE:OPTIONAL]` branches may be skipped cleanly (`- [-]`).

---

## The 5-Pillar Proactive Living Documentation Protocol

Documentation is NOT a static setup artifact or an afterthought—it is a **living architectural contract** that agents must proactively read, maintain, and expand.

### Pillar 1: Pre-Flight Context Loading ("Read Before Plan")
Before creating a ticket or claiming work (`backlog -> in-progress`), you MUST load the existing architectural context:
```python
# 1. Read project charter (vision, tech stack, constraints, boundaries)
charter = kanban_doc(action="read", project="myproj")

# 2. Read epic specification (subsystem scope, existing contracts, API patterns)
epic_spec = kanban_doc(action="read", project="myproj", epic="core")
```
*Never plan or code blindly without reading the governing charter and epic specification.*

### Pillar 2: Living Architecture Stewardship ("Evolve as You Build")
As you implement tickets, keep `project.md` and `epic.md` continuously synchronized with reality:
- **Update `project.md`** when:
  - Adding a new external dependency or runtime package.
  - Introducing new global environment variables or project-wide configurations.
  - Changing root folder structures, build scripts, or deployment targets.
- **Update `epic.md`** when:
  - Introducing a new interface, public class, function signature, or CLI flag.
  - Adding or modifying data models, database schemas, or communication protocols.
  - Resolving an architectural question or recording key design decisions.

```python
# Update epic specification with newly introduced API contracts
kanban_doc(
    action="write",
    project="myproj",
    epic="core",
    content="""# Epic Charter: Core Engine
...
## API Contracts
- `POST /api/v2/tokens`: Rotates refresh tokens (added in T004).
..."""
)
```

### Pillar 3: Supplementary Technical Knowledge Base (Beyond project.md & epic.md)
Agents are NOT restricted to `project.md` and `epic.md`. You are expected and empowered to author arbitrary supplementary technical markdown documents via `kanban_doc`:
- **Architecture Decision Records (ADRs)**:
  `kanban_doc(action="write", project="myproj", name="adr-002-jwt-rotation", content="# ADR 002: JWT Rotation\n...")`
- **Data Schemas & Protocols**:
  `kanban_doc(action="write", project="myproj", epic="core", name="storage-schema", content="# Storage Schema V2\n...")`
- **API Reference Specs**:
  `kanban_doc(action="write", project="myproj", epic="api", name="endpoints", content="# Endpoints Specification\n...")`
- **Runbooks & Operational Troubleshooting**:
  `kanban_doc(action="write", project="myproj", name="troubleshooting", content="# Failure Modes & Runbook\n...")`
- **Benchmark & Performance Reports**:
  `kanban_doc(action="write", project="myproj", epic="core", name="benchmarks", content="# Benchmark Analysis\n...")`

All custom documents authored via `kanban_doc` are automatically indexed and displayed in the web dashboard header under `docs: [project.md, adr-002-jwt-rotation, ...]` for instant multi-agent visibility.

### Pillar 4: Todo Tree Documentation Node
Every ticket that alters public contracts, CLI commands, or schemas MUST include a documentation sync step in its `## Plan (Todo Tree)` DAG:
```markdown
## Plan (Todo Tree)
- [ ] A1 [START] [lane:A] Task definition & pre-flight context verified
- [ ] A2 [lane:A] [after:A1] Core feature implementation
- [ ] A3 [lane:A] [after:A2] Living documentation & architecture sync (epic.md/ADR)
- [ ] A4 [lane:A] [after:A3] [ACCEPTANCE:MANDATORY] Observable requirement verified
- [ ] B1 [lane:B] [after:A1] [parallel] Automated regression tests & edge-case coverage
- [ ] B2 [lane:B] [after:B1] [ACCEPTANCE:MANDATORY] Test suite passes cleanly
```

### Pillar 5: QA Documentation Audit Gate
Independent `kb-qa` verifies documentation completeness during Tier 2 (The Surrounding Forest) ecosystem audit. If a ticket changed public interfaces or data contracts but failed to update `epic.md` or author an ADR, `kb-qa` will **reject the ticket back to `in-progress`**.

---

## Standard Workflow Runbook

### 1. Unified Discovery (`kanban_board`)
Discover projects, charters, epics, docs (`docs: []`), and all active tickets:
```python
kanban_board(view="overview")
```

### 2. Pre-Flight Reading, Creation & Section Population (`kanban_ticket`)
Read the governing charter and epic spec, then create and populate the ticket:
```python
kanban_doc(action="read", project="web", epic="auth")
kanban_ticket(action="create", project="web", epic="auth", title="Implement JWT refresh token rotation")
kanban_ticket(
    action="edit",
    ref="web/auth/T001",
    outcome="Refresh tokens can be rotated securely via POST /auth/refresh with replay detection.",
    scope="- Allowed: src/auth/tokens.py, tests/test_tokens.py\n- Out of scope: UI login screen",
    plan="""- [ ] A1 [START] [lane:A] Design token storage and replay detection
- [ ] A2 [lane:A] [after:A1] Implement rotation handler in tokens.py
- [ ] A3 [lane:A] [after:A2] Living documentation sync: update epic.md with /auth/refresh spec
- [ ] A4 [lane:A] [after:A3] [ACCEPTANCE:MANDATORY] Token rotation endpoint functional and replay tested
- [ ] B1 [lane:B] [after:A1] [parallel] Regression tests for expired and malformed tokens
- [ ] B2 [lane:B] [after:B1] [ACCEPTANCE:MANDATORY] Test suite passes cleanly""",
    prove="""```bash
pytest tests/test_tokens.py -v
```"""
)
```

### 3. Claiming & Starting Work (`kanban_move`)
Moving to `in-progress` atomically claims ownership with a 60-minute lease:
```python
kanban_move(ref="web/auth/T001", status="in-progress", agent_id="agent-1", note="Starting token rotation work")
```

### 4. Logging Progress, Updating Docs & Attachments (`kanban_update`)
As work progresses:
1. Complete DAG checkpoints in order with execution proof (`node_proofs`).
2. Mark untaken conditional or optional branches skipped (`skip_nodes` with `skip_reason`).
3. Update `epic.md` or author an ADR via `kanban_doc`.
4. Declare touched files and log notes:
```python
kanban_doc(action="write", project="web", epic="auth", content="... updated auth contracts ...")
kanban_update(
    ref="web/auth/T001",
    checked_nodes=["A1", "A2"],
    node_proofs={
        "A1": "Reviewed epic.md and finalized HMAC-SHA256 token rotation schema",
        "A2": "pytest tests/test_tokens.py::test_rotate -> PASS",
    },
    files=["src/auth/tokens.py", "tests/test_tokens.py"],
    notes="Finished rotation logic and updated epic.md with token specs.",
    attach_file="benchmarks/token_bench.json",
    attach_desc="Token generation latency benchmark"
)
```

### 5. Submitting for Verification (`kanban_move`)
When code is written, docs are synced, prove commands pass, and all active mandatory acceptances are completed and logged:
```python
kanban_move(ref="web/auth/T001", status="verify", note="Implementation and documentation complete, tests passing")
```

### 6. Launching Independent QA (`kb-qa`)
Invoke the `kb-qa` subagent protocol to audit the DAG execution log, minimal diff, documentation sync, surrounding ecosystem, and Horse vs. Zebra tests via `kanban_qa`.

### 7. Handling QA Rejection or Blocked States
- If `kb-qa` rejects a ticket back to `in-progress`, inspect `meta.note` and the rejection reason, fix both process gaps and code defects, and re-submit to `verify`.
- If paused by an external blocker, call `kanban_move(ref=..., status="blocked", note="<blocker reason>")`.
