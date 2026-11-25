# <img src="assets/logo.svg" alt="KanbanBoard Logo" width="40" height="40" align="absmiddle" /> KanbanBoard

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Antigravity & Claude Code](https://img.shields.io/badge/Platform-Antigravity%20%7C%20Claude%20Code-brightgreen.svg)]()
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(Python%20Stdlib)-orange.svg)]()
[![Status: Production Ready](https://img.shields.io/badge/Status-v2.0.0%20Universal-blueviolet.svg)]()

**KanbanBoard** is a universal, file-backed task orchestration and automated quality-assurance engine engineered for autonomous AI agents (Google Antigravity and Anthropic Claude Code) and human developers.

Operating entirely on local markdown files (`board/**/*.md`) and vanilla Python standard library, KanbanBoard enforces rigorous software engineering standards through **5 Mechanical Anti-Laziness Gates**, an **Executable Todo Tree DAG**, an **Atomic 60-Minute Lease Protocol**, and an independent **3-Tier QA Audit Ecosystem**.

---

## Key Features

- **Zero-Dependency & Offline-First**: Requires zero cloud accounts, external databases, or heavy Python dependencies (`PyYAML`, `requests`, `fastapi`). Runs on vanilla Python 3.8+.
- **5 Mechanical Anti-Laziness Gates**: Hard, code-level constraints that prevent AI agents from hallucinating work, skipping planning, submitting empty diffs, or self-approving tickets.
- **Executable Todo Tree (DAG)**: Hierarchical markdown checklists with branching alternative execution paths and unbroken root-to-acceptance path verification.
- **Multi-Agent 60-Minute Leases**: Prevents concurrent agent collisions via atomic move-and-claim, sliding heartbeat renewals, automatic expiration, and audited force takeovers.
- **Smart Git Verification**: Automatically differentiates between single-ticket mode (auto-discovering modified files) and multi-ticket mode (enforcing strict file declaration boundaries).
- **Safe Attachments & Architecture Charters**: Tracks benchmarks, logs, diagrams, and project/epic architectural guidelines with strict directory-traversal safeguards.
- **High-Rigor 3-Tier QA Protocol**: Dedicated `kb-qa` subagent enforcing the **Ponytail Principle** (*"The best code is the code you never wrote"*) and **Horse vs. Zebra Discriminator Testing** before burning cryptographic single-use nonces.
- **Universal Dual-Platform Layout**: Installs seamlessly into both **Google Antigravity (`agy`)** and **Claude Code** from a single unified folder.
- **Real-Time Hydrated Web Dashboard**: Built-in micro HTTP server (`viewer.py`) with automatic loopback port hunting (`7890–7899`) and instant 0ms offline data hydration.

---

## The 7 Harmonized MCP Tools

Agents interact with the board through 7 consolidated, ergonomic tools via standard I/O JSON-RPC 2.0:

| Tool | Purpose | Primary Consumer |
| :--- | :--- | :--- |
| `kanban_board` | Unified discovery, listing, and structural health checks (`overview`, `list`, `lint`). | All agents & CLI |
| `kanban_ticket` | Dual-mode inspector & creator (create ticket with template or read ticket). | All agents |
| `kanban_move` | Lifecycle transitions, atomic claims, 60m leases, and 5 mechanical gates. | Primary agents |
| `kanban_update` | In-flight progress logging, Todo Tree checkboxes, file declarations, attachments. | Ticket owner |
| `kanban_doc` | Project charter & epic architectural specification management (`docs: []`). | All agents |
| `kanban_view` | Local web dashboard launcher & MCP UI widget generator (`ui://kanban/board`). | User & agents |
| `kanban_qa` | RESTRICTED QA audit protocol for `kb-qa` (start audit & approve with nonce). | `kb-qa` ONLY |

---

## The 5 Anti-Laziness Mechanical Gates

```
[backlog] ──(Gate 1)──> [in-progress] ──(Gates 2, 3, 4)──> [verify] ──(Gate 5)──> [done]
```

1. **Gate 1: The Non-Trivial Plan Gate (`backlog -> in-progress`)**:
   Mandates $\ge 3$ tasks or $\ge 2$ hierarchy levels in `## Plan (Todo Tree)`, at least one `[ACCEPTANCE]` leaf, and rejects pre-checked acceptance tasks.
2. **Gate 2: The "Zero Work" Git Gate (`in-progress -> verify`)**:
   Queries `git status --porcelain`. Hard-rejects transition if zero files are modified or added.
3. **Gate 3: The Unbroken DAG Acceptance Path Gate (`in-progress -> verify`)**:
   Requires a continuous chain of checked (`- [x]`) tasks from the root down to at least one completed `[ACCEPTANCE]` leaf.
4. **Gate 4: The Real Prove Command Gate (`in-progress -> verify`)**:
   Rejects empty, mock (`echo`, `true`, `exit 0`), or placeholder test commands.
5. **Gate 5: Ephemeral Proof-of-QA Gate (`verify -> done`)**:
   Restricted to `kb-qa` subagent. Requires a 4-part evidence report (Diff Review, Positive Tests, Negative Discriminators, Verdict: PASS) and burns a 32-byte cryptographic nonce.

---

## Technical Documentation Wiki

Exhaustive technical documentation, architectural blueprints, and reverse-engineering manuals are maintained in the [wiki/](file:///C:/Projects/kanbanBoard/wiki/Home.md) directory:

- 📖 **[Wiki Home & Table of Contents](file:///C:/Projects/kanbanBoard/wiki/Home.md)**: System vision, architecture diagrams, and quickstart runbooks.
- 🏗️ **[System Architecture](file:///C:/Projects/kanbanBoard/wiki/Architecture.md)**: Physical directory layout, cross-process mutex locks (`board/.lock`), zero-dep parser, and execution modes.
- 🔄 **[State Machine & Lifecycle](file:///C:/Projects/kanbanBoard/wiki/State-Machine-and-Lifecycle.md)**: 5 lifecycle states, transition matrix, terminal immutability, and QA nonce lifecycle.
- 🛡️ **[The 5 Anti-Laziness Mechanical Gates](file:///C:/Projects/kanbanBoard/wiki/Anti-Laziness-Mechanical-Gates.md)**: Automated code-level validation rules preventing AI corner-cutting.
- 🌲 **[Executable Todo Tree (DAG)](file:///C:/Projects/kanbanBoard/wiki/Executable-Todo-Tree.md)**: Grammar, stack-based parser, and continuous path verification algorithm.
- 🤝 **[Multi-Agent Leases & Ownership](file:///C:/Projects/kanbanBoard/wiki/Multi-Agent-Leases-and-Ownership.md)**: Atomic move-and-claim, 60m sliding leases, heartbeat renewal, and audited force takeovers.
- 🔍 **[Smart Git Verification](file:///C:/Projects/kanbanBoard/wiki/Smart-Git-Verification.md)**: Git porcelain heuristics, single-ticket auto-merge vs multi-ticket explicit declaration.
- 📎 **[Safe Attachments & Docs](file:///C:/Projects/kanbanBoard/wiki/Safe-Attachments-and-Docs.md)**: Path traversal sanitization, attachment metadata, and project/epic architectural charters.
- 🔬 **[QA Ecosystem Protocol](file:///C:/Projects/kanbanBoard/wiki/QA-Ecosystem-Protocol.md)**: Ponytail principle, Ecosystem Blast-Radius analysis, and Horse vs. Zebra discriminator testing.
- 🔌 **[MCP Server Specification](file:///C:/Projects/kanbanBoard/wiki/MCP-Server-Specification.md)**: Zero-dep stdio JSON-RPC 2.0 protocol, 7 tool schemas, and `ui://` resources.
- 🖥️ **[Web Dashboard & Viewer](file:///C:/Projects/kanbanBoard/wiki/Web-Dashboard-and-Viewer.md)**: Dynamic port hunting (`7890–7899`), instant 0ms offline hydration (`__INITIAL_DATA__`), and live polling.
- 📦 **[Multi-Platform Distribution](file:///C:/Projects/kanbanBoard/wiki/Multi-Platform-Distribution.md)**: Single-folder universal manifest architecture for Antigravity and Claude Code.
- ⚙️ **[The Complete Reverse-Engineering Guide](file:///C:/Projects/kanbanBoard/wiki/Reverse-Engineering-Guide.md)**: Language-agnostic types, pseudo-code algorithms, and formal grammar to rebuild the system from scratch.

---

## Quickstart Guide

### 1. Installation

#### Antigravity (`agy`) Global Installation
```powershell
# Validate plugin integrity
agy plugin validate C:\Projects\kanbanBoard --strict

# Install globally
agy plugin install C:\Projects\kanbanBoard
```

#### Claude Code Installation
Add to your project's `.mcp.json` or register via Claude plugin manager:
```json
{
  "mcpServers": {
    "kanban": {
      "command": "python",
      "args": ["C:/Projects/kanbanBoard/mcp_server.py"]
    }
  }
}
```

### 2. Operator CLI Usage
```bash
# 1. View board overview
python kb.py status --overview

# 2. Create a ticket in backlog
python kb.py new --project myproj --epic core --title "Implement Auth Flow"

# 3. Move and claim ticket (sets 60m lease)
python kb.py move myproj/core/T001 in-progress --agent developer-1

# 4. Check off Todo Tree tasks and declare touched files
python kb.py update myproj/core/T001 --check "1A,1B" --files "src/auth.py" --notes "Finished hashing"

# 5. Move to verify (evaluates Gates 2, 3, and 4)
python kb.py move myproj/core/T001 verify

# 6. Launch real-time web dashboard
python viewer.py
```

### 3. Packaging Distributions
```powershell
# Builds standard .plugin archives into dist/ (zero zips)
python package.py
```

---

## License

Distributed under the MIT License. See `LICENSE` for details.
