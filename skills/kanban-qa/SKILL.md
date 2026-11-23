---
name: kanban-qa
description: High-rigor 3-tier QA protocol embodying the Ponytail philosophy ("The best code is the code you never wrote"), Ecosystem Blast-Radius analysis, Living Documentation audit, and Horse vs. Zebra discriminator testing.
---

# Kanban QA Protocol (`kb-qa`)

The `kb-qa` protocol acts as an independent gatekeeper between `verify` and `done`. Primary implementers MUST NOT self-approve tickets.

## How the Main Agent Launches `kb-qa`

When a ticket is in `verify`, the main agent invokes `kb-qa` using `invoke_subagent`:

```python
invoke_subagent(
    TypeName="self",
    Role="Kanban QA Auditor",
    Prompt="""You are the independent kb-qa auditor for ticket <ref>.
Follow the 3-Tier QA protocol strictly:
1. Initialize session: call kanban_qa(action="start", ref="<ref>") to retrieve spec and secret qa_nonce.
2. Execute 3-Tier Audit:
   - Tier 1 (The Tree): Ponytail minimal diff inspection.
   - Tier 2 (The Surrounding Forest): Ecosystem blast-radius & living documentation audit (callers, call-sites, test suite, epic.md/ADRs).
   - Tier 3: Two-pass Horse vs. Zebra discriminator testing.
3. Write substantive evidence report to evidence/<project>/<epic>/<tid>-qa.md.
4. If PASS: call kanban_qa(action="approve", ref="<ref>", qa_nonce="<qa_nonce>", evidence_path="...", note="...").
5. If FAIL: call kanban_move(ref="<ref>", status="in-progress", note="<failure reason>")."""
)
```

---

## The 3-Tier Ecosystem QA Protocol

### Tier 1: The Tree (Ponytail Diff Audit)
> *"The best code is the code you never wrote."*
- Inspect `git diff` against `files: [...]`.
- **Ruthless YAGNI**: Reject speculative abstractions, unused parameters, premature generalizations, or unrequested helpers.
- **Minimal Diff**: Reject sprawling changes when localized edits suffice.
- **Residue Check**: Zero debug logs, temporary mocks, commented-out dead code.

### Tier 2: The Surrounding Forest (Ecosystem Blast-Radius & Living Architecture)
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

## Approval Tool
Call `kanban_qa(action="approve", ref="<ref>", qa_nonce="<qa_nonce>", evidence_path="...", note="...")`.
The state engine validates the evidence report sections and burns the nonce upon approval.
