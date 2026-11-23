# /kanban-new — Create a new kanban ticket

Create a properly structured kanban ticket in `backlog` with Todo Tree DAG template.

**Steps:**

1. Ask for the project and epic slugs. If `board/` exists, inspect with `kanban_board()`.
2. Find the next available ticket ID (`T001`, `T002`, ...) in that epic.
3. Ask for a one-line title describing the observable outcome.
4. Call `kanban_ticket(ref="<project>/<epic>/<Tnnn>", title="<title>")`.
5. Guide filling in the standard sections:
   - **Outcome** — observable result from user/system perspective
   - **Scope** — allowed files vs out of scope
   - **Plan (Todo Tree)** — branching checklist with at least one `[ACCEPTANCE]` leaf tag
   - **Prove** — exact terminal commands and expected output
6. Once ready to begin work, transition to `in-progress`:
   `kanban_move(ref="<ref>", status="in-progress")`.
