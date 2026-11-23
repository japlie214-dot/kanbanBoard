---
name: kanban
description: Unified Kanban board management for Antigravity agents. Unified discovery, atomic move-and-claim, Todo Tree DAG execution, checkpoints, safe attachments, and living architectural documentation.
---

# Kanban Board Skill

This skill guides agents on interacting with the local file-backed Kanban board using the streamlined 7-tool MCP suite.

## The 7 Harmonized Tools

| Tool | Core Capability | Typical Usage |
|---|---|---|
| `kanban_board` | Discover, init, list, or lint | `kanban_board(view="overview")` or `kanban_board(view="init", project="myproj")` |
| `kanban_ticket` | Create or inspect ticket (auto-assigns ID) | `kanban_ticket(project="web", epic="auth", title="OAuth")` or `kanban_ticket(ref="web/auth/T001")` |
| `kanban_move` | Move status & claim lease | `kanban_move(ref="web/auth/T001", status="in-progress")` |
| `kanban_update` | Check nodes, log files/notes, attach | `kanban_update(ref="web/auth/T001", checked_nodes=["..."], files=["..."])` |
| `kanban_doc` | Read/write charters, epics & custom specs | `kanban_doc(action="write", project="web", name="arch", content="...")` |
| `kanban_view` | Open live web dashboard | `kanban_view()` |
| `kanban_qa` | Independent QA audit (kb-qa only) | `kanban_qa(action="start", ref="...")` & `kanban_qa(action="approve", ...)` |

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
- [ ] 1. Core implementation
  - [ ] 1A. Primary implementation branch [CHOSEN]
    - [ ] 2A. Core code logic
    - [ ] 3A. Living documentation & architecture sync (update epic.md/ADR)
    - [ ] 4A. [ACCEPTANCE] Observable requirement verified
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

### 2. Pre-Flight Reading & Ticket Creation (`kanban_ticket`)
Read the governing charter and epic spec, then create the ticket:
```python
kanban_doc(action="read", project="web", epic="auth")
kanban_ticket(ref="web/auth/T001", title="Implement JWT refresh token rotation")
```
Fill in `## Outcome`, `## Scope`, `## Plan (Todo Tree)` (including living doc step), and `## Prove`.

### 3. Claiming & Starting Work (`kanban_move`)
Moving to `in-progress` atomically claims ownership with a 60-minute lease:
```python
kanban_move(ref="web/auth/T001", status="in-progress", agent_id="antigravity", note="Starting work")
```

### 4. Logging Progress, Updating Docs & Attachments (`kanban_update`)
As work progresses:
1. Check off Todo Tree nodes.
2. Update `epic.md` or author an ADR via `kanban_doc`.
3. Declare touched files and log notes:
```python
kanban_doc(action="write", project="web", epic="auth", content="... updated auth contracts ...")
kanban_update(
    ref="web/auth/T001",
    checked_nodes=["1. Core OAuth flow", "3A. Living documentation & architecture sync"],
    files=["src/auth.py", "tests/test_auth.py"],
    notes="Finished refresh handler and updated epic.md with token specs.",
    attach_file="benchmarks/token_bench.json",
    attach_desc="Token generation latency benchmark"
)
```

### 5. Submitting for Verification (`kanban_move`)
When code is written, docs are synced, prove commands pass, and Todo Tree DAG has a complete checked path to `[ACCEPTANCE]`:
```python
kanban_move(ref="web/auth/T001", status="verify", note="Implementation and documentation complete, tests passing")
```

### 6. Launching Independent QA (`kb-qa`)
Invoke the `kb-qa` subagent protocol to audit the diff, verify documentation synchronization, inspect the surrounding ecosystem, and run Horse vs. Zebra tests via `kanban_qa`.
