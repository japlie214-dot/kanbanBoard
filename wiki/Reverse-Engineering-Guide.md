# The Complete Reverse-Engineering Guide

This document is the **definitive technical blueprint** for KanbanBoard. It contains all formal specifications, data structures, state machine algorithms, and pseudo-code necessary to completely reimplement the entire system from scratch in any programming language (Python, TypeScript, Go, Rust) without referencing the original source code.

---

## 1. Domain Data Models & Type Signatures

### 1.1 Language-Agnostic Type Schema (IDL / TypeScript)

```typescript
// Core Lifecycle Status
type TicketStatus = 'backlog' | 'in-progress' | 'verify' | 'done' | 'blocked';

// Frontmatter Attachment Record
interface Attachment {
  path: string;           // Workspace-relative path
  description: string;    // Human-readable summary
  added_at: string;       // ISO-8601 UTC timestamp
  sha256?: string;        // Optional file integrity hash
}

// Canonical Ticket Record
interface Ticket {
  id: string;                      // e.g. "T001"
  project: string;                 // Project slug e.g. "kanban-system"
  epic: string;                    // Epic slug e.g. "core"
  title: string;                   // Concise title
  status: TicketStatus;            // Lifecycle status
  owner: string | null;            // Holding agent identifier
  claimed_at: string | null;       // ISO-8601 UTC timestamp
  lease_expires_at: string | null; // ISO-8601 UTC timestamp
  files: string[];                 // Explicitly declared touched files
  docs: string[];                  // Related charters and specs
  attachments: Attachment[];       // Attached artifacts
  prove: string;                   // Concrete verification command
  body: string;                    // Raw markdown body following frontmatter
}

// Parsed Todo Tree DAG Node
interface TodoNode {
  id: string;                      // Short ID (e.g. "1A", "2.1")
  text: string;                    // Task label
  checked: boolean;                // Whether marked [x]
  is_acceptance: boolean;          // Whether tagged [ACCEPTANCE]
  depth: number;                   // Indentation depth (0 = root)
  parentId: string | null;         // Pointer to ancestor node
  childrenIds: string[];           // Pointers to descendant nodes
}
```

---

## 2. Frontmatter Parser & Serializer Algorithm

### 2.1 Parsing Algorithm
1. Read file as UTF-8 string.
2. Check if first line equals `---`. If not, treat entire file as body with empty metadata.
3. Scan lines until second `---`. Lines between form the YAML frontmatter block. Everything after is the markdown `body`.
4. Parse lines in frontmatter block line-by-line:
   - If line matches `^([A-Za-z0-9_-]+):\s*(.*)$`:
     - Key is group 1.
     - Value is group 2.
     - If Value is empty, expect an indented block (list or nested mapping) on subsequent lines.
     - If Value is scalar, strip surrounding quotes and cast:
       - `"true"` / `"false"` $\to$ boolean
       - Digits $\to$ integer / float
       - `"null"` / `""` $\to$ null / None
   - If line begins with `^\s*-\s+(.*)$`:
     - Append to active list. If item matches `key: value`, instantiate nested map.

### 2.2 Serialization Algorithm
To serialize back to disk with 100% deterministic fidelity:
```
---
id: <ticket.id>
project: <ticket.project>
epic: <ticket.epic>
title: "<ticket.title>"
status: <ticket.status>
owner: <ticket.owner or null>
claimed_at: <ticket.claimed_at or null>
lease_expires_at: <ticket.lease_expires_at or null>
files:
  - <file_1>
  - <file_2>
docs:
  - <doc_1>
attachments:
  - path: <path>
    description: "<desc>"
    added_at: <timestamp>
prove: <ticket.prove>
---
<ticket.body>
```

---

## 3. Concurrency Mutex Specification

All state-modifying operations must acquire an inter-process file lock at `board/.lock`.

```
ALGORITHM: AcquireBoardLock(timeout_seconds = 5.0)
INPUT: timeout_seconds (float)
OUTPUT: FileDescriptor (locked) or THROW TimeoutError

1. path = ResolvePath("board/.lock")
2. EnsureDirectoryExists(path.parent)
3. fd = OpenFile(path, O_CREAT | O_RDWR)
4. deadline = CurrentTimeSeconds() + timeout_seconds

5. WHILE CurrentTimeSeconds() < deadline DO
     TRY:
       IF OS == "windows" THEN:
         msvcrt.locking(fd, LK_NBLCK, 1)
       ELSE:
         fcntl.flock(fd, LOCK_EX | LOCK_NB)
       RETURN fd  // Lock acquired successfully
     CATCH (IOError, OSError):
       SleepMilliseconds(50)
   END WHILE

6. CloseFile(fd)
7. THROW TimeoutError("Could not acquire board lock within timeout")
```

---

## 4. The 5 Anti-Laziness Gates: Formal Specifications

### 4.1 Gate 1: Non-Trivial Plan Gate (`backlog` $\to$ `in-progress`)
```
FUNCTION ValidateGate1(ticket_body: String) -> Void
  nodes = ParseTodoTree(ticket_body)
  IF Length(nodes) == 0 THEN
    THROW ValidationError("Missing '## Plan (Todo Tree)' section")
  
  task_count = Length(nodes)
  max_depth = Maximum(node.depth FOR node IN nodes)
  acceptance_nodes = [node FOR node IN nodes WHERE node.is_acceptance == True]

  IF task_count < 3 AND max_depth < 2 THEN
    THROW ValidationError("Plan too trivial. Must have >= 3 tasks or >= 2 nesting levels")

  IF Length(acceptance_nodes) == 0 THEN
    THROW ValidationError("Plan must contain at least one '[ACCEPTANCE]' leaf node")

  FOR EACH node IN acceptance_nodes DO
    IF node.checked == True THEN
      THROW ValidationError("Acceptance task '" + node.text + "' cannot be pre-checked")
  END FOR
END FUNCTION
```

### 4.2 Gate 2: The "Zero Work" Git Gate (`in-progress` $\to$ `verify`)
```
FUNCTION ValidateGate2(workspace_dir: Path) -> Void
  IF NOT Exists(workspace_dir / ".git") THEN
    // Non-git fallback: verify at least one file declared and exists on disk
    RETURN
  END IF

  output = ExecuteProcess("git status --porcelain=v1", cwd=workspace_dir)
  lines = FilterNonEmptyLines(output)
  
  IF Length(lines) == 0 THEN
    THROW ZeroWorkError("Gate 2 Failed: No physical changes detected in git working tree")
  END IF
END FUNCTION
```

### 4.3 Gate 3: Unbroken DAG Acceptance Path Gate (`in-progress` $\to$ `verify`)
```
FUNCTION ValidateGate3(ticket_body: String) -> Void
  roots = ParseTodoTree(ticket_body)
  acceptance_leaves = CollectAllAcceptanceLeaves(roots)
  
  valid_path_found = False

  FOR EACH leaf IN acceptance_leaves DO
    IF leaf.checked == False THEN
      CONTINUE  // Only check completed acceptance targets
    END IF

    // Walk ancestry up to root
    curr = leaf
    path_intact = True
    WHILE curr != NULL DO
      IF curr.checked == False THEN
        path_intact = False
        BREAK
      END IF
      curr = curr.parent
    END WHILE

    IF path_intact == True THEN
      valid_path_found = True
      BREAK
    END IF
  END FOR

  IF NOT valid_path_found THEN
    THROW ValidationError("Gate 3 Failed: No unbroken checked path from root to an [ACCEPTANCE] leaf")
  END IF
END FUNCTION
```

### 4.4 Gate 4: Real Prove Command Gate (`in-progress` $\to$ `verify`)
```
FUNCTION ValidateGate4(prove_command: String) -> Void
  IF prove_command IS NULL OR Trim(prove_command) == "" THEN
    THROW ValidationError("Gate 4 Failed: 'prove:' command cannot be empty")
  END IF

  cmd = LowerCase(Trim(prove_command))
  
  MOCK_PATTERNS = ["echo ", "true", "exit 0", "<test>", "todo", "pass"]
  FOR EACH pattern IN MOCK_PATTERNS DO
    IF cmd == pattern OR StartsWith(cmd, pattern) THEN
      THROW ValidationError("Gate 4 Failed: Trivial or mock prove command rejected: " + cmd)
    END IF
  END FOR
END FUNCTION
```

### 4.5 Gate 5: Ephemeral Proof-of-QA Gate (`verify` $\to$ `done`)
```
FUNCTION ValidateGate5(ticket_ref: String, qa_nonce: String, evidence_path: Path) -> Void
  nonce_file = ResolvePath("board/.qa_nonces/" + Sanitize(ticket_ref) + ".nonce")
  
  IF NOT Exists(nonce_file) THEN
    THROW SecurityError("Gate 5 Failed: No active QA nonce found for ticket")
  END IF

  stored_nonce = Trim(ReadFile(nonce_file))
  IF stored_nonce != qa_nonce THEN
    THROW SecurityError("Gate 5 Failed: Invalid or expired QA nonce")
  END IF

  IF NOT Exists(evidence_path) OR FileSize(evidence_path) < 100 THEN
    THROW ValidationError("Gate 5 Failed: Evidence file missing or under 100 bytes")
  END IF

  content = ReadFile(evidence_path)
  MANDATORY_SECTIONS = ["## Diff Review", "## Positive Tests", "## Negative Discriminator Tests", "Verdict: PASS"]
  FOR EACH section IN MANDATORY_SECTIONS DO
    IF NOT Contains(content, section) THEN
      THROW ValidationError("Gate 5 Failed: Evidence report missing mandatory section: " + section)
    END IF
  END FOR

  // Burn nonce immediately
  DeleteFile(nonce_file)
END FUNCTION
```

---

## 5. Multi-Agent Lease & Takeover Algorithm

```
ALGORITHM: TransitionTicket(ticket_ref, target_status, calling_agent, force=False, reason="")
INPUT: ticket_ref, target_status, calling_agent, force, reason

1. WITH board_lock() DO:
     ticket = LoadTicket(ticket_ref)

     // Rule: Terminal state immutability
     IF ticket.status == "done" THEN
       THROW InvalidTransitionError("Ticket is done and cannot be transitioned")
     END IF

     // Atomic Move-and-Claim
     IF target_status == "in-progress" THEN
       ValidateGate1(ticket.body)

       now = CurrentTimeUTC()
       IF ticket.owner != NULL AND ticket.owner != calling_agent THEN
         IF now < ticket.lease_expires_at THEN
           // Active lease held by another agent
           IF force == False THEN
             THROW LeaseConflictError("Ticket held by " + ticket.owner + " until " + ticket.lease_expires_at)
           ELSE
             IF Trim(reason) == "" THEN
               THROW ValidationError("Force takeover requires non-empty reason")
             END IF
             AppendAuditLog(ticket, "Force takeover from " + ticket.owner + " by " + calling_agent + ": " + reason)
           END IF
         END IF
       END IF

       ticket.owner = calling_agent
       ticket.claimed_at = FormatISO8601(now)
       ticket.lease_expires_at = FormatISO8601(now + 3600 seconds)
       ticket.status = "in-progress"

     ELSE IF target_status == "verify" THEN
       ValidateGate2(WorkspaceRoot)
       ValidateGate3(ticket.body)
       ValidateGate4(ticket.prove)
       ticket.status = "verify"

     ELSE IF target_status == "backlog" THEN
       ticket.owner = NULL
       ticket.claimed_at = NULL
       ticket.lease_expires_at = NULL
       ticket.status = "backlog"

     ELSE IF target_status == "blocked" THEN
       ticket.status = "blocked"
     END IF

     SaveTicket(ticket)
   END WITH
```

---

## 6. Smart Git Heuristics Algorithm

```
ALGORITHM: ReconcileGitFiles(ticket)
1. board_data = GetAllBoardTickets()
2. in_progress_tickets = [t FOR t IN board_data WHERE t.status == "in-progress"]

3. IF Length(in_progress_tickets) == 1 AND in_progress_tickets[0].id == ticket.id THEN
     // Single-Ticket Mode: Auto-discover and merge
     git_files = RunGitPorcelainModifiedFiles()
     FOR EACH f IN git_files DO
       IF f NOT IN ticket.files THEN
         ticket.files.Append(f)
       END IF
     END FOR
     SaveTicket(ticket)
   ELSE
     // Multi-Ticket Mode: Enforce explicit declaration
     IF Length(ticket.files) == 0 THEN
       THROW ValidationError("Multiple tickets in-progress. You must explicitly declare touched files via kanban_update")
     END IF
   END IF
```

---

## 7. Verification Test Suite Matrix

To verify a fresh implementation from scratch, execute the following 5 verification test suites:

| Test Case | Description | Expected Output |
| :--- | :--- | :--- |
| `TC-01: Gate 1 Trivial Plan Rejection` | Submit ticket with 1 flat task. | Exception: `Plan too trivial` |
| `TC-02: Gate 1 Premature Acceptance` | Submit ticket with checked `[x]` acceptance task. | Exception: `cannot be pre-checked` |
| `TC-03: Gate 2 Zero Work Rejection` | Attempt move to `verify` with clean git tree. | Exception: `ZeroWorkError` |
| `TC-04: Gate 3 Broken Ancestor DAG` | Check acceptance leaf while parent is unchecked `- [ ]`. | Exception: `No unbroken checked path` |
| `TC-05: Gate 5 Nonce Burn Verification` | Call `kanban_qa(approve)` with valid nonce, then retry. | First call succeeds; second fails `SecurityError` (nonce burned). |
