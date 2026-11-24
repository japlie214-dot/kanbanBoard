# /kanban-qa — Launch independent 4-tier QA for a ticket in verify state

Launch the isolated `kb-qa` subagent to independently audit code diff, process execution, living docs, and run discriminator tests on a ticket in `verify` state.

**Steps:**

1. Check tickets in `verify` state with `kanban_board(view="list", status="verify")`.
2. Inspect the ticket with `kanban_ticket(action="show", ref="<ref>")`.
3. Launch exactly ONE `kb-qa` subagent per ticket (NEVER `TypeName="self"`):
   - **Antigravity (`agy`):**
     ```python
     invoke_subagent(
         TypeName="kb-qa",
         Role="Kanban QA Auditor",
         Prompt="Audit ticket <ref> in workspace <repo_root> using the 4-Tier QA protocol and certify via kanban_qa."
     )
     ```
   - **Claude Code (`cc`) / Claude Desktop:**
     Use the `Agent` tool with `subagent_type="kb-qa"` and prompt `"Audit ticket <ref> in workspace <repo_root> using the 4-Tier QA protocol and certify via kanban_qa."`.
4. Report the QA verdict back to the user.
