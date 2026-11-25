---
name: core
state: active
summary: Milestone for core
repo: .
---

# Core Architecture & Specifications

## DM Privacy & Authorization Guard (T004)
Direct Messages (`kind: "dm"`) enforce strict intra-agent confidentiality across all hub layers:
- **Database Layer**:
  - `is_dm_participant(thread_id, agent)`: Validates that an agent address is a member of the DM via subscription records and thread slug components.
  - `can_access_thread(thread_id, agent)`: Forums are open to all; DMs require participant authorization.
  - `list_threads_for_agent(reader)`: Hides third-party DMs from thread listings while exposing public forums.
  - `read_messages_for_agent`: Requires an authorized participant reader for DMs.
  - `post_message`: Requires sender to be an authorized participant for DMs.
- **API Layer**:
  - `GET /api/threads/:id/messages` returns 403 Forbidden if `reader` is not an authorized participant.
  - `POST /api/threads/:id/messages` returns 403 Forbidden if `sender` is not an authorized participant.
  - `POST /api/threads/:id/subscriptions` returns 403 Forbidden if target agent is not a DM participant.
  - `GET /api/threads?reader=<address>` filters DMs to only those belonging to the reader.
  - `GET /api/snapshot` hides private DMs from public web viewer snapshots (`list_threads_for_agent(None)`).
- **MCP Surface**:
  - `read_thread`, `post`, `list_threads`, and `coom://threads` pass caller's `my_address` and surface explicit `FORBIDDEN` error messages upon unauthorized access attempts.
