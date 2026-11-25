---
name: kanban-qa
description: High-rigor 4-tier Process + Result QA protocol: DAG Checkpoint Process Audit, Ponytail minimal diff, Ecosystem Blast-Radius & Living Documentation audit, and Horse vs. Zebra discriminator testing.
---
# Kanban QA Protocol (`kb-qa`)

The `kb-qa` subagent acts as the **sole physically authorized gatekeeper** between `verify` and `done`. Primary implementers do not have access to `kanban_qa` (`--mode work` omits it, and `PreToolUse` hooks block non-`kb-qa` callers).

## Strict Independence Contract
- **No Self-Approval**: The worker MCP server (`--mode work`) does not expose `kanban_qa`. Only the `kb-qa` subagent mounts `kanban-qa` (`--mode qa`).
- **Subagent Invocation**: Spawn an independent `kb-qa` subagent—never self-approve or reuse the author agent's conversation.

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

### Tier 2: The Surrounding Forest (Ecosystem Blast-Radius & Living Architecture)
> *"When you cut down a tree, you don't just check the tree. You check the surrounding too whether it falls into something or not."*
- **Active Regression Hunt**: Verify existing UI interactions, keyboard shortcuts, callers, and endpoints were not broken or silently altered.
- **Broader Test Suite**: Run the project's full test suite, not just the ticket's isolated unit test.
- **Side-Effects Check**: Verify global configuration, environment variables, database schemas, and shared state were not mutated unintentionally.
- **Living Documentation Audit**: Verify `epic.md`, `project.md`, or supplementary ADRs (`kanban_doc`) were updated whenever public APIs, CLI flags, schemas, or contracts changed; otherwise reject back to `in-progress`.

### Tier 3: Horse vs. Zebra Discriminator Testing
- **Pass 1 - Positive Tests ("Is it a horse?"):** Execute exact commands from `## Prove` and confirm observable outcomes match.
- **Pass 2 - Negative Discriminator Tests ("Is it NOT a zebra, donkey, mule, or cow?"):** Verify invalid/malformed/boundary inputs fail cleanly, adjacent features are untouched, and security gates cannot be bypassed.

## Writing the Evidence Report
Before approving, `kb-qa` must write `evidence/<project>/<epic>/<tid>-qa.md`:
```markdown
# QA Evidence Report: <ref>
Date: <timestamp>
Auditor: kb-qa
Nonce: <qa_nonce>

## 0. Process & Checkpoint Execution Audit
- [START] -> ...
- Cited Mandatory Checkpoints: T1, T2, ...

## 1. Minimal Diff Review
- Files modified: ...
- YAGNI & residue audit: clean

## 2. Living Architecture & Charter Audit
- epic.md / project.md status: updated / compliant

## 3. Positive Test Results
- Proof of positive test execution

## 4. Negative Discriminator Verification
- Boundary, error handling & discriminator proofs

## 5. Certification
Verdict: PASS
```

## Approval and Rejection Mechanisms
`kb-qa` can execute QA gating using either the restricted MCP tool or the CLI:

### Option A: Restricted MCP Tool (Preferred in Claude Code / Antigravity)
- **Start QA**: Call `kanban_qa(action="start", ref="<ref>")` on `kanban-qa` server to obtain the ephemeral `<qa_nonce>`.
- **Approve**: Call `kanban_qa(action="approve", ref="<ref>", qa_nonce="<qa_nonce>", evidence_path="...", note="...", workspace="<repo_root>")`.
- **Reject**: Call `kanban_qa(action="reject", ref="<ref>", qa_nonce="<qa_nonce>", evidence_path="...", note="<failure reason>")`.

### Option B: Python CLI / Library Fallback
- **Start QA**: `python kb.py qa start <ref>` (or `kb.api_qa_start(ref, kb.board_root())`).
- **Approve**: `python kb.py qa approve <ref> --nonce <nonce> --evidence <evidence_path> -n "<note>" --workspace <repo_root>` (or `kb.api_qa_approve(ref, nonce, evidence_path, note, kb.board_root(), workspace=...)`).
- **Reject**: `python kb.py qa reject <ref> --nonce <nonce> -n "<failure reason>" --evidence <evidence_path>`.
- **Board Root Helper**: Always resolve canonical centralized board using `kb.board_root()` (or alias `kb.find_board()`).
