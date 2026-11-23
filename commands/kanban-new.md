# /kanban-new — Create a new kanban ticket

Create a properly structured kanban ticket in `backlog` with Todo Tree DAG template and living documentation integration.

**Steps:**

1. **Pre-flight Reading**:
   Before planning, read the project charter and epic spec:
   ```python
   kanban_doc(action="read", project="<project>")
   kanban_doc(action="read", project="<project>", epic="<epic>")
   ```

2. **Creation**:
   Ask for the project and epic slugs (defaults to `core`), and a one-line title describing the observable outcome.
   Call `kanban_ticket(project="<project>", epic="<epic>", title="<title>")` or `kanban_ticket(ref="<project>/<epic>", title="<title>")`. The system automatically initializes the board if needed and assigns the next available ticket ID (`T001`, `T002`, etc.).

3. **Guide filling in the standard sections**:
   - **Outcome** — observable result from user/system perspective.
   - **Scope** — allowed files vs out of scope.
   - **Plan (Todo Tree)** — branching checklist with at least one `[ACCEPTANCE]` leaf tag AND a living documentation sync node:
     ```markdown
     - [ ] 1. Core Implementation
       - [ ] 1A. Primary feature branch [CHOSEN]
         - [ ] 2A. Module logic
         - [ ] 3A. Living documentation & architecture sync (update epic.md/ADR)
         - [ ] 4A. [ACCEPTANCE] Observable requirement verified
     ```
   - **Prove** — exact terminal commands and expected output.

4. **Transition to In-Progress**:
   Once ready to begin work, transition to `in-progress`:
   `kanban_move(ref="<ref>", status="in-progress")`.
