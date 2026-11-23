# Safe Attachments & Architectural Documentation Engine

Complex software features often require referencing external technical documents, database schemas, network logs, architectural decision records (ADRs), and visual mockups. 

KanbanBoard integrates a secure **Attachment Subsystem** and an **Architectural Documentation Engine** directly into the ticket ecosystem.

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

## 2. Architectural Documentation (`docs: []`) Engine

Every project and epic within KanbanBoard can define architectural charters and design documents:

```
board/
├── kanban-system/
│   ├── project.md             # Project Charter
│   └── core/
│       ├── epic.md            # Epic Architectural Specification
│       └── T001.md            # Ticket
```

### 2.1 Project Charters (`project.md`)
The project charter defines:
- **Vision & Business Objective**: Why does this project exist?
- **Architecture Overview**: System components and dependencies.
- **Tech Stack & Standards**: Coding conventions, required linting rules, test coverage targets.
- **Security & Compliance Constraints**: Blast radius policies.

### 2.2 Epic Specifications (`epic.md`)
The epic specification defines:
- **Scope & Out-of-Scope Boundaries**: What belongs to this epic vs. future epics.
- **API Contracts**: REST, gRPC, or MCP interfaces being introduced.
- **Acceptance Milestones**: Key delivery criteria.

### 2.3 Automatic Ticket Indexing (`docs: []`)
When a ticket is created or inspected, the engine automatically populates its `docs: []` frontmatter list with the paths to its governing charters:
```yaml
docs:
  - kanban-system/project.md
  - kanban-system/core/epic.md
```

### 2.4 Unified Documentation API (`kanban_doc`)
Agents read and author documentation seamlessly using the `kanban_doc` tool:

```python
# Read project charter
charter = kanban_doc(action="read", project="kanban-system")

# Read epic specification
epic_spec = kanban_doc(action="read", project="kanban-system", epic="core")

# Author or update architectural documentation
kanban_doc(
    action="write",
    project="kanban-system",
    epic="core",
    name="data-flow.md",
    content="# Data Flow Specification\n..."
)
```

### 2.5 Board Overview Discovery
When an agent calls `kanban_board(view='overview')`, the returned payload includes not just tickets, but also the full index of all project charters, epic specifications, and supplementary docs. This provides an agent with complete architectural context in a single tool call.
