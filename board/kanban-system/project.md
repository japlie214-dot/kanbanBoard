---
name: kanban-system
state: active
summary: Universal Kanban board management and strict multi-agent execution framework with DAG Todo Trees, 5 Anti-Laziness Gates, and real-time observability.
repo: .
---

# kanban-system

`kanban-system` is the canonical architectural and execution engine powering the Kanban Board plugin across Claude Code, Codex, and Google Antigravity.

## Core Responsibilities
1. **Strict DAG Workflow**: Every ticket enforces an acyclic directed graph with `[START]`, explicit dependencies (`[after:...]`), terminal acceptance nodes (`[ACCEPTANCE:MANDATORY|OPTIONAL]`), and execution proof requirements.
2. **5 Anti-Laziness Gates**:
   - Non-Trivial Plan Gate (`backlog -> in-progress`)
   - Zero Work Git Gate (`in-progress -> verify`)
   - Mandatory DAG & Process Proof Gate (`in-progress -> verify`)
   - Real Prove Command Gate (`in-progress -> verify`)
   - Ephemeral Proof-of-QA Gate (`verify -> done` via `kb-qa`)
3. **Multi-Agent Coordination & Leases**: Ownership is tracked with automatic lease expiration and takeover mechanisms.
4. **Living Documentation Stewardship**: Continual synchronization between code reality and project charters/epic specs.
5. **Real-time Observability**: Zero-latency loopback web dashboard with instant `__INITIAL_DATA__` hydration and responsive ticket inspector.
