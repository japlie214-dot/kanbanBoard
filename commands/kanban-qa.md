# /kanban-qa — Launch independent 4-tier QA for a ticket in verify state

Launch the `kb-qa` subagent to independently audit code diff, process execution, living docs, and run discriminator tests on a ticket in `verify` state.

**Steps:**

1. Check tickets in `verify` state with `kanban_board(view="list", status="verify")`.
2. Inspect the ticket with `kanban_ticket(ref="<ref>")`.
3. Launch exactly ONE `kb-qa` subagent per ticket:
   ```python
   invoke_subagent(
       TypeName="self",
       Role="Kanban QA Auditor",
       Prompt="""You are the independent kb-qa auditor for ticket <ref>.
   Follow the 4-Tier Process + Result QA protocol strictly:
   1. Initialize session: call kanban_qa(action="start", ref="<ref>") to retrieve spec, DAG, Execution Log, and secret qa_nonce.
   2. Execute 4-Tier Audit:
      - Tier 0: Process & Checkpoint Audit (verify checkpoints from [START] to all mandatory acceptances with ## Execution Log proofs).
      - Tier 1: Diff audit for bloat and unnecessary abstractions (Ponytail philosophy).
      - Tier 2: Ecosystem blast-radius & living documentation audit (callers, test suites, epic.md/ADRs).
      - Tier 3: Positive tests ("Is it a horse?") and negative discriminator tests ("Is it NOT a zebra?").
   3. Write evidence report to evidence/<project>/<epic>/<tid>-qa.md.
   4. If PASS: call kanban_qa(action="approve", ref="<ref>", qa_nonce="<qa_nonce>", evidence_path="...", note="...").
   5. If FAIL: call kanban_qa(action="reject", ref="<ref>", qa_nonce="<qa_nonce>", note="<failure reason>")."""
   )
   ```
4. Report the QA verdict back to the user.
