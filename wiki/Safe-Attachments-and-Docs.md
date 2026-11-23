# Safe Attachments & Living Architectural Documentation Engine

Complex software systems require referencing external technical documents, database schemas, network logs, architectural decision records (ADRs), and visual mockups. 

KanbanBoard integrates a secure **Attachment Subsystem** and a **Living Architectural Documentation Engine** (`docs: []`) directly into the ticket ecosystem.

---

## 1. The Safe Attachment Subsystem

Tickets can record file attachments directly within their YAML frontmatter under the `attachments:` key:

```yaml
attachments:
  - path: docs/architecture/auth_flow.png
    description: High-level sequence diagram
    added_at: '2026-11-20T08:15:00Z'
    sha256: 3a7f8b9c...
```

### 1.1 Path Boundary Security Rules
To prevent malicious directory traversal attacks (e.g., an agent accidentally attaching system credentials like `/etc/passwd` or `C:\Windows\System32\config\SAM`):
1. **Workspace Boundary Constraint**: All attachment paths must resolve to a location inside the current project root or workspace tree.
2. **Path Traversal Sanitization**: Rejects paths containing relative escape sequences (`../..`) that resolve outside the workspace root.
3. **Symlink Resolution**: Resolves symlinks using `Path.resolve()` to verify the physical canonical target before acceptance.
4. **Normalized POSIX Slashes**: All Windows backslashes (`\`) are normalized to forward slashes (`/`) for cross-platform portability.

### 1.2 MCP & CLI Operations
```python
# Attach a file to a ticket via MCP
kanban_update(
    ref="myproj/core/T001",
    attach_file="benchmarks/results.json",
    attach_desc="Throughput benchmark before optimization"
)

# Detach a file
kanban_update(
    ref="myproj/core/T001",
    detach_file="benchmarks/results.json"
)
```

---

## 2. Living Architectural Documentation (`docs: []`) Engine

Documentation in KanbanBoard is **executable architecture context** shared across multi-agent runtimes (Claude Code, Codex, Antigravity).

```
board/
├── kanban-system/
│   ├── project.md             # Project Charter
│   ├── adr-001-caching.md     # Architecture Decision Record
│   └── core/
│       ├── epic.md            # Epic Architectural Specification
│       ├── schema.md          # Subsystem Schema Specification
│       └── T001.md            # Ticket
```

### 2.1 The 5-Pillar Proactive Documentation Protocol

1. **Pre-Flight Reading ("Read Before Plan")**:
   Agents MUST inspect `project.md` and `epic.md` before creating or claiming tickets:
   ```python
   charter = kanban_doc(action="read", project="kanban-system")
   epic_spec = kanban_doc(action="read", project="kanban-system", epic="core")
   ```

2. **Living Architecture Stewardship ("Evolve as You Build")**:
   - `project.md` defines the global mission, tech stack, constraints, and dependencies. Update it when global dependencies, build scripts, or environment variables change.
   - `epic.md` defines subsystem scope, API contracts, interfaces, and acceptance milestones. Update it whenever new interfaces, commands, or data models are added.

3. **Supplementary Technical Knowledge Base (Beyond project.md & epic.md)**:
   Agents can create and maintain arbitrary supplementary markdown documents:
   - **ADRs (Architecture Decision Records)**: `kanban_doc(action="write", project="...", name="adr-002-jwt", content="...")`
   - **Data Schemas & Protocols**: `kanban_doc(action="write", project="...", epic="...", name="schema-v2", content="...")`
   - **API Specs & Contracts**: `kanban_doc(action="write", project="...", epic="...", name="endpoints", content="...")`
   - **Troubleshooting & Runbooks**: `kanban_doc(action="write", project="...", name="runbook", content="...")`
   - **Performance Benchmarks**: `kanban_doc(action="write", project="...", epic="...", name="benchmarks", content="...")`

4. **Todo Tree Documentation Node**:
   Tickets modifying public interfaces must include a living documentation step in their Todo Tree DAG:
   ```markdown
   - [ ] 3A. Living documentation & architecture sync (update epic.md/ADR)
   ```

5. **QA Documentation Audit Gate**:
   The independent `kb-qa` auditor inspects documentation synchronization during Tier 2 (The Surrounding Forest) ecosystem audit. Tickets failing to update charters or author specs when contracts changed are rejected back to `in-progress`.

### 2.2 Automatic Indexing & Dashboard Discovery
When documents are added to a project or epic, the dashboard and `kanban_board(view="overview")` automatically list them:
```yaml
docs:
  - kanban-system/project.md
  - kanban-system/adr-001-caching.md
  - kanban-system/core/epic.md
  - kanban-system/core/schema.md
```
Every active agent can query, read, and cross-reference these documents without leaving the Kanban toolchain.
