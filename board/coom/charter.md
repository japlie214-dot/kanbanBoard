# Project Charter: Coom (coommunity)

## Mission
Provide a zero-dependency, ultra-low-latency local communication and coordination hub connecting multiple AI coding agent runtimes with equal, first-class fidelity:
- **Claude Code CLI & Claude Desktop (`cc`)**
- **Codex CLI (`codex`)**
- **Antigravity CLI (`agy`)**

## Key Objectives
1. **Tri-Runtime Parity**:
   - Equal first-class developer ergonomics across all 3 ecosystems:
     - Universal CLI shorthand binary: `coom` (alongside `coommunity`).
     - Claude Code custom command: `/coom` (`.claude/commands/coom.md`).
     - Codex CLI custom prompt: `/coom` (`.codex/prompts/coom.md`).
     - Antigravity custom slash command: `/coom` (`skills/coom/SKILL.md`).
2. **Masterclass Documentation**:
   - Comprehensive, deeply technical wiki in `wiki/` explaining the internal mechanics of Claude Code named pipes, Codex app-server WebSocket RPC, and Antigravity session resumption.
3. **Rock-Solid Multi-Agent Orchestration**:
   - 3-tier delivery dispatcher (Tier 1 Live Push, Tier 2 Headless Wake, Tier 3 Pull/Hook Banners) with anti-loop circuit breakers, hop counting, and real-time SSE observability.
