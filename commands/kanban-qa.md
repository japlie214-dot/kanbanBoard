# /kanban-qa — Launch independent 3-tier QA for a ticket in verify state

Launch the `kb-qa` subagent to independently audit code diff and run discriminator tests on a ticket in `verify` state.

**Steps:**

1. Check tickets in `verify` state with `kanban_board(view="list", status="verify")`.
2. Inspect the ticket with `kanban_ticket(ref="<ref>")`.
3. Launch exactly ONE `kb-qa` subagent per ticket:
   ```json
   Agent(
     subagent_type="kb-qa",
     prompt="Verify ticket <ref>.\nWork root: <root>\nAllowed files: <files>\nEntry points: <commands>"
   )
   ```
4. `kb-qa` will:
   - Initialize session: `kanban_qa(action="start", ref="<ref>")` to fetch secret `qa_nonce`.
   - Tier 1: Diff audit for bloat and unnecessary abstractions (Ponytail philosophy).
   - Tier 2: Ecosystem blast-radius audit (callers, call-sites, broader test suite).
   - Tier 3: Positive tests ("Is it a horse?") and negative discriminator tests ("Is it NOT a zebra?").
   - Write `evidence/<ref>-qa.md`.
   - Call `kanban_qa(action="approve", ref="<ref>", qa_nonce="<nonce>", evidence_path="...", note="...")` if passing, or `kanban_move(ref="<ref>", status="in-progress", note="...")` if failing.
5. Report the QA verdict back to the user.
