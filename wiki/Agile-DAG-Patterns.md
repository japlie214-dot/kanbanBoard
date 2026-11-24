# Agile DAG Todo Tree Patterns & Execution Guide

The **Todo Tree** is not a static linear checklist. In traditional software workflows, linear "waterfall" plans (`Step 1 -> Step 2 -> Step 3 -> Step 4`) create fragile failure traps for autonomous agents: if unexpected friction occurs at Step 2 (e.g. an incompatible dependency, a headless environment, an unroutable socket, or an ambiguous interface), the agent gets stuck in a retry loop or must retreat and discard its entire plan.

A **True Directed Acyclic Graph (DAG)** enables **Adaptive Contingency Topologies**. Agents account for uncertainty upfront by encoding decision forks (`[when:if/else]`), parallel swarms (`[parallel]`), alternative convergences (`[after:A|B]`), and graceful degradation (`[optional]`, `[after:...,opt?]`).

---

## 1. The 4 Canonical Agile DAG Patterns

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

#### Markdown Template:
```markdown
## Plan (Todo Tree)
- [ ] A1 [START] [lane:main] Probe environment, dependencies & verify baseline assumptions
- [ ] B1 [lane:fast] [after:A1] [when:if(fast_path_viable):fork1] Fast-path primary implementation
- [ ] B2 [lane:fallback] [after:A1] [when:else(fast_path_viable):fork1] Fallback/contingency polyfill implementation
- [ ] A2 [lane:main] [after:B1|B2] Integrate core solution with chosen branch
- [ ] T1 [lane:test] [after:A2] [ACCEPTANCE:MANDATORY] Chosen path functional and regression tests pass
```
- **In-Flight Agility**: If `A1` probe succeeds, execute `B1` and call `kanban_update(skip_nodes=['B2'], skip_reason='native API supported; skipped fallback')`. The XOR join `[after:B1|B2]` is immediately satisfied and `A2` unblocks without delay.

---

### Pattern 2: Concurrent Multi-Lane Swarming (Parallel Independence)
**When to Use**: When work decomposes into independent workstreams (e.g. Backend logic, Frontend UI, Test harness, or Documentation) that have zero shared mutable state.

```
                         [START]
               ┌────────────┼────────────┐
               │            │            │
            [lane:A]     [lane:B]     [lane:C]
           Core Backend  Frontend UI  Test Harness
            (Node A1)   [parallel]   [parallel]
               │            │            │
               └────────────┼────────────┘
                            ▼
                     [after:A1,B1,C1]
                  Integration Acceptance
```

#### Markdown Template:
```markdown
## Plan (Todo Tree)
- [ ] A1 [START] [lane:core] Implement core engine schema and validation logic
- [ ] B1 [lane:ui] [after:A1] [parallel] Implement responsive component layout and view rendering
- [ ] C1 [lane:test] [after:A1] [parallel] Author unit and edge-case test suite
- [ ] T1 [lane:test] [after:A1,B1,C1] [ACCEPTANCE:MANDATORY] End-to-end integration verified across all lanes
```

---

### Pattern 3: Graceful Degradation & Optional Polish
**When to Use**: When a ticket has essential functional requirements alongside non-critical enhancements (e.g. telemetry caching, animations, visual indicators, or secondary doc guides).

```
    [START] -> A1. Core Implementation -> T1. [ACCEPTANCE:MANDATORY]
                      │
               [optional] lane:polish
               O1. Fancy Animation / Cache
                      │
               O2. [ACCEPTANCE:OPTIONAL]
                      │
    [after:T1,O2?] T2. Final Living Architecture Sync
```

#### Markdown Template:
```markdown
## Plan (Todo Tree)
- [ ] A1 [START] [lane:core] Implement core functional logic and interfaces
- [ ] T1 [lane:test] [after:A1] [ACCEPTANCE:MANDATORY] Core functional requirements pass verification
- [ ] O1 [lane:polish] [after:A1] [optional] Optional visual animation or performance caching enhancement
- [ ] O2 [lane:polish] [after:O1] [ACCEPTANCE:OPTIONAL] Optional enhancement verified
- [ ] T2 [lane:docs] [after:T1,O2?] [ACCEPTANCE:MANDATORY] Synchronize living architecture documentation
```
- **Conditional Join (`[after:T1,O2?]`)**: If `O1`/`O2` is skipped via `kanban_update(skip_nodes=['O1','O2'])`, `T2` is not blocked! Core delivery is never held hostage by optional polish.

---

### Pattern 4: Dual-Track Discriminator (Horse vs. Zebra)
**When to Use**: High-rigor QA verification ensuring both positive acceptance and negative refusal boundaries are proven simultaneously.

```
       [START] -> A1. Implementation -> A2. Integration
                           │
                 ┌─────────┴─────────┐
                 │                   │
           [lane:positive]     [lane:negative] [parallel]
            T1. Valid Inputs    T2. Malformed / Unauthorized
            Expected: HTTP 200  Expected: HTTP 400/403 Rejected
                 │                   │
                 └─────────┬─────────┘
                           ▼
                  [after:T1,T2]
           T3. [ACCEPTANCE:MANDATORY] Full Security Gate
```

---

## 2. Multi-Agent Execution Behaviors for `[parallel]`

When `ready_nodes` reports multiple unblocked checkpoints across parallel lanes:

### Mode A: Subagent Delegation (Google Antigravity / Swarm)
- In runtimes with subagent tools (`invoke_subagent`, `run_workflow`, `swarm`):
  1. The coordinator agent claims the primary lane (e.g. `lane:core`).
  2. The coordinator spawns a subagent to own the parallel lane (e.g. `invoke_subagent(Role="UI Specialist", Prompt="...")`).
  3. The subagent executes the checkpoint and records proof via `kanban_update(ref, checked_nodes=['B1'], node_proofs={'B1': ...})`.
  4. Both agents work simultaneously; the coordinator resumes once parallel branches converge.

### Mode B: Standalone Batching (Claude Code / Codex Single-Agent)
- In single-agent runtimes without subagent spawning:
  1. **Batching**: The agent issues independent tool calls for both lanes in a single turn.
  2. **Non-Blocking Resilience**: If Lane A is waiting on user input or a long compilation, the agent immediately switches to Lane B without retreating or idling.
  3. **Order Independence**: Checkpoints are checked off as each finishes.

### Mode C: Tri-Runtime Swarm (Connecting CC, Codex & AGY via `coom`)
- In cross-agent collaborative environments:
  1. The leasing agent invites a peer agent via `coom` message: `@claude-code Lane B is ready on ui/T004`.
  2. Claude Code checks out the workspace, completes Lane B, and updates the board.

---

## 3. Instant Scaffolding Tooling

Agents no longer need to write DAGs by hand. Use the built-in scaffolding helpers:

### Via MCP:
```json
kanban_ticket(action="scaffold", pattern="agile")
```
Supported patterns: `"agile"`, `"feature"`, `"spike"`, `"refactor"`.

Or create a ticket directly with automatic scaffolding:
```json
kanban_ticket(action="create", project="kanban-system", epic="core", title="Feature Name", pattern="agile")
```

### Via CLI:
```bash
python kb.py scaffold --pattern agile
python kb.py create web/auth/T005 "OAuth Token Rotation" --pattern agile
```
