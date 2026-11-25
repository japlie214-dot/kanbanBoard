---
name: kanban
description: Universal Kanban board management for AI coding agents (Antigravity, Claude Code, Codex). Unified discovery, atomic move-and-claim, true DAG Todo Tree execution with process proofs, safe attachments, and living architectural documentation.
---

# Kanban Board Skill: Agile DAG Execution Engine

This skill guides agents on interacting with the local file-backed Kanban board using the streamlined 7-tool Model Context Protocol (MCP) suite.

---

## The 7 Harmonized Tools

| Tool | Core Capability | Typical Usage |
|---|---|---|
| `kanban_board` | Discover, init, list, or lint | `kanban_board(view="overview")` or `kanban_board(view="lint")` |
| `kanban_ticket` | Create, inspect, scaffold, or edit | `kanban_ticket(action="create", project="web", epic="auth", title="OAuth", pattern="agile")` or `kanban_ticket(action="scaffold", pattern="agile")` |
| `kanban_move` | Move status & claim lease (supports `force` + `reason`) | `kanban_move(ref="web/auth/T001", status="in-progress", agent_id="agent-1")` |
| `kanban_update` | Check off checkpoints with proofs, skip branches (`- [-]`), declare files/notes | `kanban_update(ref="web/auth/T001", checked_nodes=["A1"], node_proofs={"A1": "pytest -> pass"})` |
| `kanban_doc` | Read, write, or list charters, epics & custom specs (`name` optional) | `kanban_doc(action="read", project="web", epic="auth")` or `kanban_doc(action="list", project="web")` |
| `kanban_view` | Open live web dashboard | `kanban_view()` |
| `kanban_qa` | Independent QA audit (kb-qa only: `start`, `approve`, `reject`) | `kanban_qa(action="start", ref="...")` |

---

## 1. The Agile DAG Mindset (Branching vs. Waterfall Fragility)

### Why Linear Waterfall Plans Fail Autonomous Agents
In traditional checklists, agents predict a sequential path:
$$\text{Step 1} \rightarrow \text{Step 2} \rightarrow \text{Step 3} \rightarrow \text{Step 4}$$
When unexpected friction hits Step 2 (e.g. missing dependency, headless environment, unroutable port, or permission denial), a waterfall agent gets trapped in a retry loop or must retreat and discard its entire plan.

### How a True DAG Delivers Agility
The **Todo Tree** is an **Adaptive Contingency Topology**. Rather than pretending the future is 100% predictable, an agent encodes decision forks (`[when:if/else]`), fallback paths (`[after:A|B]`), independent swarms (`[parallel]`), and graceful degradation (`[optional]`, `[after:...,opt?]`) into the initial ticket plan.

---

## 2. The 4 Canonical Agile DAG Patterns

### Pattern 1: Feasibility Spike & Contingency Fork (Spike & Fallback)
**When to Use**: When attempting a new library, native OS feature, or performance optimization where success cannot be guaranteed in all environments.
```
       [START] -> A1. Probe target environment / API
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
         [if:fast_viable]    [else:fast_viable]
          B1. Fast Native     B2. Emulated Fallback
                 │                   │
                 └─────────┬─────────┘
                           ▼
                  [after:B1|B2]
             A2. Converge & Integrate Core
```
- **Markdown Scaffolding**:
  ```markdown
  ## Plan (Todo Tree)
  - [ ] A1 [START] [lane:main] Probe environment, dependencies & verify baseline assumptions
  - [ ] B1 [lane:fast] [after:A1] [when:if(fast_path_viable):fork1] Fast-path primary implementation
  - [ ] B2 [lane:fallback] [after:A1] [when:else(fast_path_viable):fork1] Fallback/contingency polyfill implementation
  - [ ] A2 [lane:main] [after:B1|B2] Integrate core solution with chosen branch
  - [ ] T1 [lane:test] [after:A2] [ACCEPTANCE:MANDATORY] Chosen path functional and regression tests pass
  ```
- **In-Flight Pivot**: If `A1` succeeds, execute `B1` and call `kanban_update(skip_nodes=['B2'], skip_reason='native API supported; skipped fallback')`. The XOR join `[after:B1|B2]` is immediately satisfied and `A2` unblocks without hesitation!

### Pattern 2: Concurrent Multi-Lane Swarming (Parallel Independence)
**When to Use**: When work decomposes into independent workstreams (e.g. Core Engine, Web UI, Test Harness, or Docs) that have zero shared mutable state.
```markdown
## Plan (Todo Tree)
- [ ] A1 [START] [lane:core] Implement core engine schema and validation logic
- [ ] B1 [lane:ui] [after:A1] [parallel] Implement responsive component layout and view rendering
- [ ] C1 [lane:test] [after:A1] [parallel] Author unit and edge-case test suite
- [ ] T1 [lane:test] [after:A1,B1,C1] [ACCEPTANCE:MANDATORY] End-to-end integration verified across all lanes
```

### Pattern 3: Graceful Degradation & Optional Polish
**When to Use**: When a ticket has essential functional requirements alongside non-critical enhancements (e.g. telemetry caching, animations, visual indicators, or secondary doc guides).
```markdown
## Plan (Todo Tree)
- [ ] A1 [START] [lane:core] Implement core functional logic and interfaces
- [ ] T1 [lane:test] [after:A1] [ACCEPTANCE:MANDATORY] Core functional requirements pass verification
- [ ] O1 [lane:polish] [after:A1] [optional] Optional visual animation or performance caching enhancement
- [ ] O2 [lane:polish] [after:O1] [ACCEPTANCE:OPTIONAL] Optional enhancement verified
- [ ] T2 [lane:docs] [after:T1,O2?] [ACCEPTANCE:MANDATORY] Synchronize living architecture documentation
```
- **Conditional Join (`[after:T1,O2?]`)**: If `O1`/`O2` is skipped via `kanban_update(skip_nodes=['O1','O2'])`, `T2` is **not blocked**! Core delivery is never held hostage by optional polish.

### Pattern 4: Dual-Track Discriminator (Horse vs. Zebra)
**When to Use**: High-rigor QA verification ensuring both positive acceptance and negative refusal boundaries are proven simultaneously.
```markdown
## Plan (Todo Tree)
- [ ] A1 [START] [lane:core] Implement feature logic
- [ ] T1 [lane:test] [after:A1] [ACCEPTANCE:MANDATORY] Positive functional requirements verified (valid input succeeds)
- [ ] T2 [lane:test] [after:A1] [parallel] [ACCEPTANCE:MANDATORY] Negative Discriminator: Malformed inputs and unauthorized actions rejected
```

---

## 3. Multi-Agent Execution Behaviors for `[parallel]` & QA Handover

- **Parallel Workstreams (`[parallel]`)**: Use swarm, subagents, or workflow for `[parallel]` lanes.
- **Asynchronous QA Handover**: Spawn `kb-qa` once the ticket is in `verify`. While waiting for `kb-qa`, work on another ticket if available.

---

## 4. Dynamic In-Flight Agility & Lenient Proof Logging

### Instant Scaffolding (Never Write Complex DAGs by Hand)
To avoid manual syntax errors, generate ready-to-use DAG templates:
```python
# Generate template
template = kanban_ticket(action="scaffold", pattern="agile")

# Or create ticket directly with scaffolded agile DAG
kanban_ticket(action="create", project="myproj", epic="core", title="Feature Name", pattern="agile")
```
Supported patterns: `"agile"`, `"feature"`, `"spike"`, `"refactor"`.

### In-Flight Pivoting via `skip_nodes`
When a decision fork or optional branch is untaken, skip it cleanly:
```python
kanban_update(
    ref="myproj/core/T001",
    skip_nodes=["B2"],
    skip_reason="Native OS API probe succeeded; skipping fallback polyfill."
)
```

### Lenient Execution Proof Formats
When recording proofs, `kanban_update` automatically formats the log. If editing markdown directly, both canonical and human formats are recognized:
- Canonical: `- [2026-11-23 08:00 UTC] [DONE] A1 | proof: pytest passed`
- Human: `- Node A1: pytest tests/test_core.py passed with 10 assertions`
- Bracketed: `- [A1]: Ran benchmarks showing 42ms latency`

---

## 5. The 5-Pillar Proactive Living Documentation Protocol

Documentation is NOT a static setup artifact—it is a **living architectural contract**:

### Pillar 1: Pre-Flight Context Loading ("Read Before Plan")
```python
charter = kanban_doc(action="read", project="myproj")
epic_spec = kanban_doc(action="read", project="myproj", epic="core")
```

### Pillar 2: Living Architecture Stewardship ("Evolve as You Build")
- **Update `project.md`** when adding runtime packages, environment variables, or build workflows.
- **Update `epic.md`** when introducing interfaces, public functions, CLI flags, database schemas, or communication protocols.

### Pillar 3: Supplementary Technical Knowledge Base
Agents are empowered to author arbitrary supplementary technical markdown documents via `kanban_doc`:
- ADRs: `kanban_doc(action="write", project="myproj", name="adr-002-jwt-rotation", content="...")`
- Schemas: `kanban_doc(action="write", project="myproj", epic="core", name="storage-schema", content="...")`

### Pillar 4: Todo Tree Documentation Node
Every ticket altering public contracts or schemas must include a living documentation sync item in its DAG.

### Pillar 5: QA Documentation Audit Gate
`kb-qa` verifies documentation completeness during Tier 2 ecosystem audit. If contracts changed without updating `epic.md` or authoring an ADR, `kb-qa` will reject the ticket back to `in-progress`.

---

## 6. Standard Workflow Runbook

```python
# 1. Discover board state
kanban_board(view="overview")

# 2. Pre-flight reading & scaffold ticket
kanban_doc(action="read", project="web", epic="auth")
kanban_ticket(action="create", project="web", epic="auth", title="OAuth Token Rotation", pattern="agile")

# 3. Claim ticket with 60-min lease
kanban_move(ref="web/auth/T001", status="in-progress", agent_id="agent-1", note="Starting work")

# 4. In-flight execution & proof logging
kanban_update(
    ref="web/auth/T001",
    checked_nodes=["A1", "B1"],
    node_proofs={"A1": "Environment probed; native crypto verified", "B1": "Token rotation implemented"},
    skip_nodes=["B2"],
    skip_reason="Native crypto supported; polyfill not needed",
    files=["src/auth.py", "tests/test_auth.py"]
)

# 5. Move to verify
kanban_move(ref="web/auth/T001", status="verify", note="Implementation and regression tests complete")

# 6. Launch independent QA audit (kb-qa)
# kb-qa runs kanban_qa(action="start"), verifies 4-tier evidence, and approves to done
```
