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
  - `kanban_ticket`: Inspection, creation, DAG scaffolding (`action="scaffold", pattern="agile|feature|spike|refactor"`), and in-place DAG/spec edits.
  - `kanban_move`: Lifecycle transitions with atomic claiming.
  - `kanban_update`: Checkpoint check-offs with execution proofs, branch skipping (`- [-]`), dynamic `ready_nodes` reporting, and attachment management.
  - `kanban_doc`: Pre-flight reading and living documentation updates.
  - `kanban_view`: Local browser visualization trigger.
  - `kanban_qa`: Restricted 4-tier audit and nonce-backed certification (`start`, `approve`, `reject`).
- **Agile DAG Scaffolding & Lenient Proof Engine**:
  - `api_scaffold_dag`: Generates mathematically valid, pre-validated DAG templates.
  - Lenient `parse_execution_log`: Accepts both standard timestamped proofs and human markdown formats (`- Node A1: ...`, `- [A1]: ...`).
  - Flexible Regex QA Header Matching: Allows natural report variations in section titles during `api_qa_approve`.
- **Ponytail Anti-Cheat Protocol**: Cryptographic ephemeral nonces generated per QA session preventing direct transitions to `done`.
