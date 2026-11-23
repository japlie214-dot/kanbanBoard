# /kanban-move — Move a ticket through its lifecycle

Move a kanban ticket to a new status using native MCP tools, enforcing the 5 Anti-Laziness Gates.

**Steps:**

1. Inspect the ticket with `kanban_ticket(ref="<ref>")`.
2. Target status options:
   - `backlog`: Shelve / pause an unworked or deprioritized ticket
   - `in-progress`: Actively working (atomically claims ticket with 60m lease; requires valid Todo Tree DAG)
   - `verify`: Implementation finished, physical git changes verified, unbroken DAG path completed, waiting for QA
   - `blocked`: Work paused due to an external impediment (note required)
   - `done`: **RESTRICTED**. Cannot be moved directly via this command. Requires launching `/kanban-qa`.
3. Call `kanban_move(ref="<ref>", status="<status>", note="<optional note>", force=False)`.
4. While working in `in-progress`, record checkpoints, check off DAG nodes, or attach files with `kanban_update(ref="<ref>", ...)`.
