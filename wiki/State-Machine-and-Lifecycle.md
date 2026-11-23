# State Machine & Ticket Lifecycle

At the core of KanbanBoard is a deterministic finite-state automaton (FSA). Every piece of work must transition through strictly governed lifecycle phases.

---

## 1. The 5 Lifecycle States

```mermaid
stateDiagram-v2
    [*] --> backlog : Create ticket
    
    backlog --> in_progress : Move & Claim (Gate 1 Passed)
    in_progress --> backlog : Release / Stalled
    
    in_progress --> verify : Finish Work (Gates 2, 3, 4 Passed)
    verify --> in_progress : QA Rejected (Diff/Test Failure)
    
    verify --> done : kb-qa Certified (Gate 5 Passed)
    
    backlog --> blocked : External Impediment
    in_progress --> blocked : External Impediment
    verify --> blocked : External Impediment
    blocked --> backlog : Impediment Cleared
    blocked --> in_progress : Impediment Cleared
    blocked --> verify : Impediment Cleared
    
    done --> [*] : Terminal Immutable State
```

| State | Role & Description | Allowed Actor |
| :--- | :--- | :--- |
| `backlog` | Unassigned work item. Plan may be in draft. No active lock or lease. | Any agent / human |
| `in-progress` | Actively owned by an agent with a valid 60-minute sliding lease. | Ticket Owner only |
| `verify` | Implementation complete. Git changes verified. Locked for QA review. | Owner transitions to `verify` |
| `done` | **Terminal state.** Certified by independent `kb-qa` subagent with burned nonce. | `kb-qa` ONLY |
| `blocked` | Paused due to an external blocker (dependency, human input needed). | Any agent / human |

---

## 2. Transition Matrix & Permitted Moves

| Current State | Target State | Prerequisites & Mandatory Enforcements | Actor |
| :--- | :--- | :--- | :--- |
| `[*]` | `backlog` | Initial creation with Todo Tree template. | Anyone |
| `backlog` | `in-progress` | **Gate 1**: Valid non-trivial Todo Tree plan ($\ge 2$ levels or $\ge 3$ tasks, at least one unchecked `[ACCEPTANCE]` leaf). Claims 60m lease. | Primary Agent |
| `in-progress` | `verify` | **Gate 2**: Working git changes detected (`git status --porcelain`).<br>**Gate 3**: Unbroken DAG path from root to checked `[ACCEPTANCE]` leaf.<br>**Gate 4**: Concrete prove command (no mocks/echoes). | Ticket Owner |
| `verify` | `done` | **Gate 5**: `kanban_qa(action='approve')` called with valid ephemeral `qa_nonce` and conforming 4-part evidence report. | `kb-qa` ONLY |
| `verify` | `in-progress` | QA rejection. Nonce invalidated. Explanatory note added to ticket. | `kb-qa` / Owner |
| Any (except `done`) | `blocked` | Mandatory explanatory reason provided in `note`. | Any |
| `blocked` | Previous State | Unblocking note provided. | Any |

---

## 3. Terminal State Immutability

Once a ticket enters `done`, it is **permanently immutable**:
- Neither primary agents nor `kb-qa` can modify its frontmatter, Todo Tree, attachments, or status.
- Attempts to call `kanban_move` or `kanban_update` on a `done` ticket trigger a hard exception:
  ```
  InvalidTransitionError: Ticket 'myproj/core/T001' is in terminal state 'done' and cannot be modified.
  ```
- **Administrative Override**: If a finished ticket genuinely needs to be reopened due to regressions, a human operator must run the explicit CLI command:
  ```bash
  python kb.py move myproj/core/T001 backlog --force --reason "Regression identified in production audit"
  ```

---

## 4. Cryptographic QA Nonce Lifecycle

To prevent prompt injection, privilege escalation, or unauthorized self-approval by primary agents, ticket approval requires an ephemeral single-use token called a **QA Nonce**.

```mermaid
sequenceDiagram
    autonumber
    actor Primary as Primary Agent
    actor QA as kb-qa Auditor Subagent
    participant Engine as Kanban Engine (kb.py)
    participant NonceStore as board/.qa_nonces/

    Primary->>Engine: kanban_move(ref, 'verify')
    Note over Engine: Validates Gates 2, 3, 4.<br/>Status becomes 'verify'.
    Engine-->>Primary: Ticket moved to verify. Ready for kb-qa.

    QA->>Engine: kanban_qa(action='start', ref)
    Engine->>Engine: Generate 32-byte secure hex token (nonce)
    Engine->>NonceStore: Write token to <project>_<epic>_<id>.nonce
    Engine-->>QA: Return ticket spec, files, prove command, and QA Nonce

    Note over QA: Independent 3-Tier Audit:<br/>1. Diff blast-radius<br/>2. Positive tests<br/>3. Negative discriminator tests<br/>4. Writes evidence file

    QA->>Engine: kanban_qa(action='approve', ref, qa_nonce, evidence_path)
    Engine->>NonceStore: Read & verify nonce matches disk
    Engine->>Engine: Validate Gate 5 (Evidence report structure)
    Engine->>NonceStore: Delete (burn) nonce file immediately
    Engine->>Engine: Transition ticket status to 'done'
    Engine-->>QA: Ticket certified and marked done!
```

### 4.1 Security Properties of the Nonce
1. **Single-Use Burn**: As soon as `kanban_qa(action='approve')` succeeds, the nonce file is permanently deleted (`unlink`). It cannot be reused.
2. **Restricted Access**: Only the `kanban_qa` tool can issue or burn nonces. The standard `kanban_move` tool rejects moves to `done` outright.
3. **No Nonce Forwarding**: If a ticket is rejected back to `in-progress`, any existing nonce file is deleted. When moved back to `verify`, a fresh nonce must be generated.
