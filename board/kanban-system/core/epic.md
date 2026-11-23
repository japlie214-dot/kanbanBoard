---
name: core
state: active
summary: Core lifecycle engine, DAG validation, atomic lease ownership, anti-cheat nonce gates, and QA verification protocol.
repo: .
---

# Core Lifecycle & Validation Engine

The `core` epic encapsulates the underlying Python state engine (`kb.py`), CLI interfaces, and the Model Context Protocol (MCP) server (`mcp_server.py`).

## Key Components
- **`kb.py`**: The definitive source of truth for ticket parsing, YAML frontmatter manipulation, acyclic DAG topological sorting, proof verification, lease management, and QA gating.
- **`mcp_server.py`**: Exposes the 7 harmonized MCP tools:
  - `kanban_board`: Unified discovery, listing, initialization, and linting.
  - `kanban_ticket`: Inspection, creation, and in-place DAG/spec edits.
  - `kanban_move`: Lifecycle transitions with atomic claiming.
  - `kanban_update`: Checkpoint check-offs, branch skipping (`- [-]`), execution proofs, and attachment management.
  - `kanban_doc`: Pre-flight reading and living documentation updates.
  - `kanban_view`: Local browser visualization trigger.
  - `kanban_qa`: Restricted 4-tier audit and nonce-backed certification.
- **Ponytail Anti-Cheat Protocol**: Cryptographic ephemeral nonces generated per QA session preventing direct transitions to `done`.
