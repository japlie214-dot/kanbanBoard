# Multi-Platform Distribution Architecture

KanbanBoard is engineered as a **universal single-folder repository** that simultaneously serves as a fully compliant native plugin for both **Google Antigravity (`agy`)** and **Anthropic Claude Code**.

---

## 1. Universal Layout Specification

Rather than maintaining separate repositories or branched codebases for each platform, KanbanBoard maps platform-specific manifests to a single shared execution core:

```
kanbanBoard/
├── dist/                                 # Built .plugin packages (zero zips)
│   ├── kanbanBoard.plugin               # Canonical universal distribution
│   └── kanban-board.plugin              # Backward-compatible link
│
├── [Antigravity Native Manifests]
│   ├── plugin.json                       # Antigravity plugin manifest (v2.0.0)
│   ├── mcp_config.json                   # Antigravity MCP server definition
│   ├── rules/AGENTS.md                   # Strict behavioral rules & 5 mechanical gates
│   └── skills/                           # Antigravity skill definitions
│       ├── kanban/SKILL.md               # Main developer skill
│       └── kanban-qa/SKILL.md            # Independent QA auditor skill
│
├── [Claude Code Native Manifests]
│   ├── .claude-plugin/plugin.json        # Claude Code plugin definition
│   ├── .mcp.json                         # Claude Code MCP server config
│   ├── CLAUDE.md                         # Claude Code system prompt & tool guide
│   ├── commands/                         # Claude custom slash commands (/kanban-*)
│   │   ├── kanban-new.md
│   │   ├── kanban-move.md
│   │   ├── kanban-status.md
│   │   └── kanban-qa.md
│   └── agents/                           # Claude dedicated subagent definitions
│       └── kb-qa.md                      # Dedicated kb-qa auditor subagent
│
├── [Shared Python Runtime Core]
│   ├── kb.py                             # Core engine, state machine, gates, parser
│   ├── mcp_server.py                     # 7-tool stdio JSON-RPC MCP server
│   ├── viewer.py                         # Dynamic-port loopback HTTP dashboard
│   ├── apps/Board.bat                    # Windows desktop launcher
│   ├── resources/board.html              # Hydrated SPA dashboard
│   └── tests/test_kanban.py              # Test suite verifying all gates & state engine
│
└── [Documentation & Build]
    ├── README.md                         # Master overview & operator runbook
    ├── package.py                        # Automated .plugin packager
    └── wiki/                             # Technical wiki & reverse-engineering guide
```

---

## 2. Platform Manifest Contracts

### 2.1 Antigravity Plugin Contract (`plugin.json`)
```json
{
  "name": "kanban-board",
  "version": "2.0.0",
  "description": "Structured Kanban task tracking, quality-gated verification, and interactive view-only web dashboard.",
  "author": "Antigravity Team",
  "license": "MIT",
  "mcp": {
    "configFile": "mcp_config.json"
  },
  "rules": [
    "rules/AGENTS.md"
  ],
  "skills": [
    "skills/kanban",
    "skills/kanban-qa"
  ]
}
```

### 2.2 Claude Code Plugin Contract (`.claude-plugin/plugin.json`)
```json
{
  "name": "kanban-board",
  "version": "2.0.0",
  "description": "Structured Kanban board with 5 mechanical verification gates and independent kb-qa auditor.",
  "author": "Antigravity Team",
  "mcpServers": {
    "kanban": {
      "command": "python",
      "args": ["${pluginDirectory}/mcp_server.py"]
    }
  }
}
```

---

## 3. Packaging & Distribution Protocol (`package.py`)

Packaging produces standard POSIX-compliant `.plugin` files inside `dist/`:

1. **Format**: Standard ZIP container with extension `.plugin`.
2. **POSIX Path Normalization**: All directory separators within the archive are strictly forward slashes (`/`), preventing decompression issues on Linux/macOS.
3. **Executable Bit Preservation**: Python scripts (`*.py`) and launchers (`*.bat`) are assigned Unix file attributes `0o755 << 16`, while documentation and assets receive `0o644 << 16`.
4. **Stray ZIP Erasure**: Automatically scans and unlinks any legacy `.zip` archives.

### 3.1 Verification Commands
```powershell
# Build plugin packages into dist/
python package.py

# Validate strict Antigravity plugin compliance
agy plugin validate C:\Projects\kanbanBoard --strict

# Install globally into Antigravity
agy plugin install C:\Projects\kanbanBoard
```
