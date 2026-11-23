# Multi-Agent Leases & Ownership Model

In modern agentic environments, multiple AI agents (e.g., Claude Code, Antigravity, subagents, and background workers) may operate concurrently in the same repository. Without strict concurrency controls, agents can trample each other's code, duplicate work, or introduce conflicting changes.

KanbanBoard incorporates an atomic, file-backed **Lease & Ownership Model** directly into ticket metadata.

---

## 1. Ownership Schema & Attributes

Every ticket's YAML frontmatter contains three explicit ownership attributes:

```yaml
owner: agent-alpha                    # Unique identifier of the holding agent
claimed_at: '2026-11-20T08:00:00Z'    # ISO-8601 UTC timestamp of initial claim
lease_expires_at: '2026-11-20T09:00:00Z' # Sliding expiration deadline (now + 60m)
```

---

## 2. Atomic Move-and-Claim Protocol

In KanbanBoard, claiming a ticket is **never a disconnected two-step process**. Instead, the act of claiming is atomically coupled with transitioning a ticket into active work:

$$\text{backlog} \xrightarrow{\text{kanban\_move}(ref, \, \text{'in-progress'}, \, \text{agent\_id})} \text{in-progress} + \text{Claim}$$

```mermaid
sequenceDiagram
    autonumber
    actor Agent as Primary Agent (claude-1)
    participant Engine as Kanban Engine
    participant Ticket as board/proj/epic/T001.md

    Agent->>Engine: kanban_move(ref, 'in-progress', agent_id='claude-1')
    Note over Engine: Check board lock<br/>Check Gate 1 (Plan complexity)<br/>Check existing owner & lease
    Engine->>Ticket: Set status: in-progress<br/>Set owner: claude-1<br/>Set claimed_at: UTC now<br/>Set lease_expires_at: UTC now + 60m
    Engine-->>Agent: Ticket claimed successfully! Lease valid for 60m.
```

---

## 3. Sliding Lease Heartbeat Renewal

AI development runs can encounter long builds, large test suites, or multi-turn agent investigations. To prevent active agents from losing their tickets prematurely while ensuring dead agents release their hold:

1. **Default Window**: Initial lease duration is exactly **60 minutes**.
2. **Heartbeat via Progress**: Whenever an agent performs productive work via `kanban_update(ref, checked_nodes=..., notes=...)`, the engine automatically resets the lease deadline:
   $$\text{lease\_expires\_at} \leftarrow \text{UTC\_NOW}() + 60\,\text{minutes}$$
3. **No Phantom Locks**: If an agent process crashes or disconnects, the ticket remains protected for up to 60 minutes, after which it becomes free for takeover.

---

## 4. Automatic Expiration & Force Takeover Protocol

```mermaid
flowchart TD
    Req["Agent 'agent-beta' calls kanban_move(ref, 'in-progress')"]
    CheckOwner{"Is ticket owned\nby another agent?"}
    CheckTime{"Has lease expired?\n(now > lease_expires_at)"}
    CheckForce{"Is force=True\nand reason provided?"}
    
    Allow["Grant ownership to agent-beta\nReset 60m lease"]
    RejectBusy["REJECT:\nTicket held by agent-alpha\nuntil expires_at"]
    RejectNoReason["REJECT:\nForce takeover requires non-empty reason"]
    Audit["Log takeover audit note to ticket:\n'Force takeover from agent-alpha: <reason>'"]

    Req --> CheckOwner
    CheckOwner -- No --> Allow
    CheckOwner -- Yes --> CheckTime
    CheckTime -- Yes (Expired) --> Allow
    CheckTime -- No (Active) --> CheckForce
    CheckForce -- No --> RejectBusy
    CheckForce -- Yes (No reason) --> RejectNoReason
    CheckForce -- Yes (With reason) --> Audit --> Allow
```

### 4.1 Force Takeover Audit Trail
When an urgent takeover is required before the 60-minute expiration (e.g. human operator intervention or agent reboot), the caller must pass `force=True` and a mandatory `reason`:

```python
kanban_move(
    ref="myproj/core/T001",
    status="in-progress",
    agent_id="agent-beta",
    force=True,
    reason="agent-alpha disconnected after unhandled exception in build runner"
)
```

The engine logs an immutable audit event directly into the ticket body:
```markdown
> [!WARNING]
> **Takeover Event** (2026-11-20T08:35:12Z):
> Ticket forcefully claimed by `agent-beta` from `agent-alpha`.
> **Reason**: agent-alpha disconnected after unhandled exception in build runner.
```

---

## 5. Voluntary Release & Unclaiming

An agent can cleanly relinquish a ticket without abandoning work by moving it back to `backlog` or calling `kanban_move` with a note:
- Moving `in-progress` $\to$ `backlog` clears the `owner`, `claimed_at`, and `lease_expires_at` frontmatter fields.
- Work done on the Todo Tree and declared files is preserved on disk for the next agent to resume.
