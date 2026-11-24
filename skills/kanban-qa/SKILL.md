---
name: kanban-qa
description: High-rigor 4-tier Process + Result QA protocol: DAG Checkpoint Process Audit, Ponytail minimal diff, Ecosystem Blast-Radius & Living Documentation audit, and Horse vs. Zebra discriminator testing.
---

# Kanban QA Protocol (`kb-qa`)

The `kb-qa` protocol acts as an independent gatekeeper between `verify` and `done`. Primary implementers MUST NOT self-approve tickets.

## Strict Independence Contract
- **No Self-Approval**: The agent that authored the code MUST NOT self-sign `kanban_qa(action="approve")` in the same conversation turn. Doing so invalidates QA rigor through author confirmation bias.
- **Subagent Invocation**: When a ticket reaches `verify`, the implementing agent MUST spawn an independent subagent via `invoke_subagent(TypeName="self", Role="Kanban QA Auditor", Model="inherit"|"pro", ...)` to conduct the audit with clean context.

## How the Main Agent Launches `kb-qa`

When a ticket is in `verify`, the main agent invokes `kb-qa` using `invoke_subagent`:

```python
invoke_subagent(
    TypeName="self",
    Role="Kanban QA Auditor",
    Model="inherit",
    Prompt="""You are the independent kb-qa auditor for ticket <ref>.
Follow the 4-Tier Process + Result QA protocol strictly:
1. Initialize session: call kanban_qa(action="start", ref="<ref>") to retrieve spec, DAG, Execution Log, and secret qa_nonce.
2. Execute 4-Tier Audit:
   - Tier 0 (Process & Checkpoint Audit): Verify ALL checkpoints from [START] to ALL mandatory [ACCEPTANCE:MANDATORY] nodes are checked AND actually executed with real proof in ## Execution Log (no rubber-stamping, valid if/else decisions, chronological order).
   - Tier 1 (The Tree): Ponytail minimal diff inspection.
   - Tier 2 (The Surrounding Forest): Ecosystem blast-radius & living documentation audit (callers, call-sites, test suite, epic.md/ADRs). Check for REGRESSIONS in previously working functionality!
   - Tier 3: Two-pass Horse vs. Zebra discriminator testing (both positive proofs and refusal of invalid inputs).
3. Write substantive evidence report to evidence/<project>/<epic>/<tid>-qa.md.
4. If PASS: call kanban_qa(action="approve", ref="<ref>", qa_nonce="<qa_nonce>", evidence_path="...", note="...").
5. If FAIL: call kanban_qa(action="reject", ref="<ref>", qa_nonce="<qa_nonce>", evidence_path="...", note="<failure reason>")."""
)
```

---

## The 4-Tier Process & Ecosystem QA Protocol

### Tier 0: Process & Checkpoint Execution Audit ("Did they actually run the process?")
> *"Verify not just the final result, but that every checkpoint from START to every mandatory acceptance was genuinely executed."*
- Verify every active path from `[START]` to **all** `[ACCEPTANCE:MANDATORY]` nodes is `- [x]`.
- Inspect `## Execution Log`: verify timestamps, chronological dependency order, and substantive per-node proofs (reject bulk rubber-stamped checkboxes or vague proofs like "done").
- Verify `if/else` branch decisions match actual code/environment conditions, and that skipped optional/else branches are cleanly marked `- [-]`.
- Spot-check intermediate checkpoint artifacts/commands to confirm the process actually happened.

### Tier 1: The Tree (Ponytail Diff Audit)
> *"The best code is the code you never wrote."*
- Inspect `git diff` against `files: [...]`.
- **Ruthless YAGNI**: Reject speculative abstractions, unused parameters, premature generalizations, or unrequested helpers.
- **Minimal Diff**: Reject sprawling changes when localized edits suffice.
- **Residue Check**: Zero debug logs, temporary mocks, commented-out dead code.

### Tier 2: The Surrounding Forest (Ecosystem Blast-Radius & Anti-Regression Verification)
> *"Did the new change break any existing contract, component, or user-facing capability?"*
- **Active Regression Hunt**: Verify that existing UI interactions, keyboard shortcuts, or components were NOT replaced, disabled, or broken (e.g. if styling was updated, can sections still fold/unfold? Can cards still be clicked? Did existing endpoints stop working?).
- **Documentation Enforcement**: Reject if public interfaces, schemas, or CLI commands were altered without updating `epic.md` or adding supplementary docs (`kanban_doc`).
- **Test Suite Integrity**: Run full test suite, ensuring existing tests still pass without regressions.
> *"When you cut down a tree, you don't just check the tree. You check the surrounding too whether it falls into something or not."*
- **Callers & Call-Sites**: Audit every caller of modified functions. Did any changed signature or return type cause silent failures?
- **Broader Test Suite**: Do not just run the ticket's isolated unit test! Run the project's broader test suite to verify adjacent features did not break.
- **Side-Effects Check**: Verify global configuration, environment variables, database schemas, and shared state were not mutated unintentionally.
- **Living Documentation Audit**:
  - Did this ticket introduce new public APIs, CLI flags, configuration variables, database schemas, or architectural patterns?
  - If **YES**, verify that the implementer updated `epic.md` or `project.md`, or authored a supplementary spec/ADR via `kanban_doc`.
  - If documentation was neglected despite contract changes, **reject ticket back to `in-progress`** with note: *"Missing architectural documentation update in epic.md or supplementary spec"*.

### Tier 3: Horse vs. Zebra Discriminator Testing
- **Pass 1 — Positive Tests ("Is it a horse?"):**
  - Execute exact commands from `## Prove`.
  - Confirm observable outcomes and acceptance criteria match.
- **Pass 2 — Negative Discriminator Tests ("Is it NOT a zebra, donkey, mule, or cow?"):**
  - Verify invalid, malformed, or boundary inputs fail with proper errors (never silent failure, unexpected coercion, or crash).
  - Verify adjacent features, commands, or data were NOT altered or broken.
  - Verify security/permission gates cannot be bypassed with look-alike inputs.

---

## Writing the Evidence Report
Before approving, `kb-qa` must write `evidence/<project>/<epic>/<tid>-qa.md`:
```markdown
# QA Evidence Report: <ref>
Date: <timestamp>
Verdict: PASS

## 0. Process & Checkpoint Audit
- Verified Mandatory Acceptances: <e.g. A4, B2>
- Execution Log & Dependency Order: <All checkpoints from START verified with real proofs>
- Branch Decisions (if/else & optional): <Verified taken/skipped branches match reality>

## 1. Diff & Blast Radius Review
- Tree Scope: <Minimal diff verified, zero unrequested bloat>
- Surrounding Forest: <Callers and adjacent test suites verified>
- Living Architecture & Docs: <epic.md updated with new contracts / ADR authored / No contract changes required>

## 2. Pass 1 — Positive Tests ("Is it a horse?")
- Test: <command>
  Result: PASS

## 3. Pass 2 — Negative Discriminator Tests ("Is it NOT a zebra?")
- Test: <invalid input command>
  Result: PASS (refused with expected error)
```

## Approval and Rejection Tools
- **Approve**: Call `kanban_qa(action="approve", ref="<ref>", qa_nonce="<qa_nonce>", evidence_path="...", note="...")`. The state engine validates the 4-tier evidence report sections, verifies all mandatory acceptance IDs are cited, and burns the nonce upon certification to `done`.
- **Reject**: Call `kanban_qa(action="reject", ref="<ref>", qa_nonce="<qa_nonce>", note="<failure reason>", evidence_path="...")`. Burns the nonce, logs the failure reason, and transitions the ticket back to `in-progress`.
