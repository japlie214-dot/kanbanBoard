# The 5 Anti-Laziness Mechanical Gates

Large Language Models (LLMs) executing multi-turn development tasks are inherently prone to cognitive shortcuts: skipping edge case verification, checking off tasks without executing code, marking tickets done with zero git diff, and running trivial assertions (`echo "tests pass"`).

KanbanBoard replaces conversational honor systems with **deterministic, code-level mechanical gates**. Every critical state transition is intercepted and audited by the state engine.

---

## Gate 1: The Non-Trivial Plan Gate (`backlog` $\to$ `in-progress`)

### Objective
Prevents agents from claiming tickets before articulating an executable, structured plan of work.

### Specification
When an agent moves a ticket from `backlog` to `in-progress`:
1. The ticket body **must contain** a section header `## Plan (Todo Tree)`.
2. The tree **must satisfy structural complexity thresholds**:
   $$\text{tasks} \ge 3 \quad \lor \quad \text{nesting\_depth} \ge 2$$
3. The tree **must contain at least one explicit acceptance leaf**, marked with the `[ACCEPTANCE]` tag.
4. **Premature Completion Rejection**: Every `[ACCEPTANCE]` task must be unchecked (`- [ ]`) at the moment of transition. If any acceptance leaf is already checked (`- [x]`), the transition is hard-rejected.

### Enforcement Logic (from `kb.py`)
```python
def validate_plan_gate(content: str):
    nodes = parse_todo_tree(content)
    if not nodes:
        raise ValidationError("Gate 1 Failed: Ticket missing '## Plan (Todo Tree)' section.")
    
    total_tasks = len(nodes)
    max_depth = max(n.depth for n in nodes) if nodes else 0
    acceptance_nodes = [n for n in nodes if n.is_acceptance]

    if total_tasks < 3 and max_depth < 2:
        raise ValidationError(
            f"Gate 1 Failed: Plan is too trivial ({total_tasks} tasks, depth {max_depth}). "
            "Must have >= 3 tasks or >= 2 hierarchy levels."
        )

    if not acceptance_nodes:
        raise ValidationError("Gate 1 Failed: Plan must contain at least one '[ACCEPTANCE]' leaf node.")

    premature = [n for n in acceptance_nodes if n.checked]
    if premature:
        raise ValidationError(
            f"Gate 1 Failed: Acceptance task '{premature[0].text}' is already checked! "
            "Cannot claim ticket with pre-completed acceptance criteria."
        )
```

---

## Gate 2: The "Zero Work" Git Gate (`in-progress` $\to$ `verify`)

### Objective
Prevents agents from claiming completion when no actual physical code changes exist on disk.

### Specification
When moving from `in-progress` to `verify`:
1. The engine invokes `git status --porcelain=v1` inside the repository root.
2. The output is parsed into staged, unstaged, and untracked modifications.
3. If the total number of modified or added files is **zero**:
   $$\sum (\text{staged} + \text{unstaged} + \text{untracked}) = 0$$
   The transition is **hard-rejected**. An agent cannot proceed to verification without modified code.

---

## Gate 3: The Unbroken DAG Acceptance Path Gate (`in-progress` $\to$ `verify`)

### Objective
Verifies that the agent actually executed a coherent sequence of steps culminating in at least one finished acceptance criterion.

### Specification
1. The Todo Tree is parsed into an Directed Acyclic Graph (DAG) of parent-child tasks.
2. The engine computes all valid root-to-acceptance paths:
   $$\mathcal{P} = \{ (v_0, v_1, \dots, v_k) \mid v_0 \in \text{Roots}, \, v_k \in \text{AcceptanceLeaves} \}$$
3. The gate requires that **at least one path** $P^* \in \mathcal{P}$ has all constituent nodes marked checked (`- [x]`):
   $$\exists P^* \in \mathcal{P} \quad \text{s.t.} \quad \forall v \in P^*, \, \text{checked}(v) = \text{True}$$
4. If an acceptance leaf is checked, but its parent or ancestor steps are unchecked, the gate rejects the move.

```
Valid Path:
[x] 1. Core Logic
  [x] 1.1 Implementation
    [x] 1.1.1 Verify Spec [ACCEPTANCE]    <-- PASSED (Solid chain of [x])

Invalid Path:
[ ] 1. Core Logic
  [ ] 1.1 Implementation
    [x] 1.1.1 Verify Spec [ACCEPTANCE]    <-- REJECTED (Broken ancestor chain)
```

---

## Gate 4: The Real Prove Command Gate (`in-progress` $\to$ `verify`)

### Objective
Prevents agents from passing verification using mock commands, empty echoes, or placeholder test strings.

### Specification
The frontmatter `prove:` attribute must define a concrete, testable command:
1. Cannot be empty or null.
2. Must not contain mock command patterns:
   - `echo ...`
   - `true`
   - `exit 0`
   - Placeholder tokens: `<test>`, `TODO`, `pytest ... (placeholder)`
3. Must reference executable test frameworks or test files (e.g., `pytest tests/`, `python -m unittest tests/test_*.py`, `npm test`, `cargo test`).

---

## Gate 5: Ephemeral Proof-of-QA Gate (`verify` $\to$ `done`)

### Objective
Restricts final certification exclusively to an independent `kb-qa` subagent and mandates a comprehensive, 4-part evidence artifact.

### Specification
When `kanban_qa(action='approve')` is called:
1. **Nonce Verification**: The provided `qa_nonce` must match the cryptographic 32-byte token stored at `board/.qa_nonces/<ticket>.nonce`.
2. **Evidence File Inspection**: The file at `evidence_path` must exist and be non-empty ($> 100$ bytes).
3. **Mandatory Report Structure**: The file must contain all four mandatory architectural sections:
   - `## Diff Review` (Detailed review of every modified hunk)
   - `## Positive Tests` (Evidence that requested features work)
   - `## Negative Discriminator Tests` (Horse vs. Zebra test cases proving rejection of invalid inputs)
   - `Verdict: PASS`
4. **Immediate Nonce Burn**: Upon successful validation, the nonce file is unlinked from disk before the ticket status is updated to `done`.
