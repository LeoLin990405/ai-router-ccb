# CCB - Multi-AI Collaboration Platform

<p align="center">
  <strong>Intelligent Multi-AI Orchestration with 9 Providers and Specialized Agents</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#agents">Agents</a> •
  <a href="#providers">Providers</a> •
  <a href="#installation">Installation</a>
</p>

**English** | [中文](README_zh.md)

---

## Acknowledgements

This project stands on the shoulders of giants. Special thanks to:

- **[bfly123/claude_code_bridge](https://github.com/bfly123/claude_code_bridge)** - The original multi-AI collaboration framework that inspired this project. Thank you for pioneering the concept of bridging multiple AI assistants!

- **[Grafbase/Nexus](https://github.com/grafbase/nexus)** - Inspiration for our intelligent routing engine. Their work on AI gateway architecture influenced our unified router design.

- **[code-yeongyu/oh-my-opencode](https://github.com/code-yeongyu/oh-my-opencode)** - Inspiration for agent orchestration patterns, the Sisyphus agent concept, and magic keyword system.

---

## Features

### Core Capabilities
- **9 AI Providers**: Claude, Codex, Gemini, OpenCode, DeepSeek, Droid, iFlow, Kimi, Qwen
- **Intelligent Routing**: Auto-select optimal provider based on task type
- **Magic Keywords**: `@deep`, `@review`, `@all` trigger special behaviors
- **Unified Interface**: Consistent commands across all providers

### Specialized Agents (9 Agents)
| Agent | Purpose | Primary Providers |
|-------|---------|-------------------|
| **Sisyphus** | Code implementation | Codex, Gemini |
| **Oracle** | Deep reasoning & analysis | DeepSeek, Claude |
| **Librarian** | Documentation & search | Claude, Gemini |
| **Explorer** | Codebase navigation | Gemini, Claude |
| **Frontend** | UI/UX development | Gemini, Claude |
| **Reviewer** | Code review & testing | Gemini, Claude |
| **Workflow** | Multi-step automation | iFlow, Droid |
| **Polyglot** | Translation & multilingual | Kimi, Qwen |
| **Autonomous** | Long-running tasks | Droid, Codex |

### Advanced Features
- **Rate Limiting**: Token bucket algorithm per provider
- **MCP Aggregation**: Unified tool discovery across servers
- **OAuth2 Authentication**: Secure Web API access
- **LSP/AST Tools**: Code intelligence with tree-sitter
- **Hooks & Skills**: Extensible plugin system
- **Performance Analytics**: Track latency, success rates
- **Smart Caching**: Reduce redundant requests
- **Batch Processing**: Parallel task execution

---

## Quick Start

```bash
# Smart routing - auto-selects best provider
ccb ask "Add a React component"        # → gemini (frontend)
ccb ask "Design an API endpoint"       # → codex (backend)
ccb ask "Analyze algorithm complexity" # → deepseek (reasoning)

# Magic keywords
ccb ask "@deep analyze this algorithm"   # Force deep reasoning
ccb ask "@review check this code"        # Force code review
ccb ask "@all what's the best approach"  # Multi-provider query

# Agent execution
ccb-agent auto "implement sorting function"  # Auto-select agent
ccb-agent execute reviewer "audit this code" # Specific agent

# Provider commands
cask "your question"   # Codex
gask "your question"   # Gemini
dskask "your question" # DeepSeek
```

---

## Agents

### Agent Selection
```bash
# List all agents
ccb-agent list

# Auto-select best agent for task
ccb-agent auto "your task description"

# Execute with specific agent
ccb-agent execute <agent> "task"

# Show which agent would be selected
ccb-agent match "your task"
```

### Agent Capabilities

| Capability | Agents | Keywords |
|------------|--------|----------|
| Code Writing | Sisyphus, Frontend, Autonomous | implement, create, build |
| Code Review | Reviewer | review, audit, check |
| Reasoning | Oracle | analyze, reason, algorithm |
| Documentation | Librarian, Polyglot | document, explain, translate |
| Navigation | Explorer | find, search, locate |
| Workflow | Workflow | automate, pipeline, process |
| Translation | Polyglot | translate, multilingual |
| Long Tasks | Autonomous | background, long-running |

---

## Providers

| Provider | Ask | Ping | Best For |
|----------|-----|------|----------|
| Claude | `lask` | `lping` | Architecture, general queries |
| Codex | `cask` | `cping` | Backend, API development |
| Gemini | `gask` | `gping` | Frontend, code review |
| OpenCode | `oask` | `oping` | General coding |
| DeepSeek | `dskask` | `dskping` | Deep reasoning, algorithms |
| Droid | `dask` | `dping` | Autonomous execution |
| iFlow | `iask` | `iping` | Workflow automation |
| Kimi | `kask` | `kping` | Chinese, long context |
| Qwen | `qask` | `qping` | Multilingual |

---

## Routing Rules

| Task Type | Keywords | File Patterns | Provider |
|-----------|----------|---------------|----------|
| Frontend | react, vue, component | `*.tsx`, `*.vue` | Gemini |
| Backend | api, endpoint, server | `api/**`, `routes/**` | Codex |
| Reasoning | analyze, algorithm | - | DeepSeek |
| Architecture | design, architect | - | Claude |
| Review | review, check, audit | - | Gemini |

### Magic Keywords

| Keyword | Action | Description |
|---------|--------|-------------|
| `@deep` | Deep reasoning | Force DeepSeek |
| `@review` | Code review | Force Gemini review mode |
| `@docs` | Documentation | Query Context7 |
| `@search` | Web search | Trigger web search |
| `@all` | Multi-provider | Query multiple providers |

---

## Installation

### Prerequisites
- [WezTerm](https://wezfurlong.org/wezterm/) or tmux
- Provider CLIs: `claude`, `codex`, `gemini`, etc.

### Install
```bash
git clone https://github.com/LeoLin990405/ccb.git ~/.local/share/codex-dual
cd ~/.local/share/codex-dual && ./install.sh
```

### Environment Variables
```bash
# Add to ~/.zshrc or ~/.bashrc
export CCB_SIDECAR_AUTOSTART=1
export CCB_SIDECAR_DIRECTION=right
export CCB_CLI_READY_WAIT_S=20
```

---

## Commands

### CCB Commands
```bash
ccb ask "question"           # Smart routing
ccb route "message"          # Show routing decision
ccb health                   # Check provider health
ccb magic                    # List magic keywords

# Task management
ccb tasks list
ccb tasks stats

# Performance
ccb stats
ccb cache stats

# Batch processing
ccb batch run -f tasks.txt

# Web dashboard
ccb web
```

### Agent Commands
```bash
ccb-agent list               # List agents
ccb-agent auto "task"        # Auto-select agent
ccb-agent execute <agent> "task"
ccb-agent match "task"       # Show matching agent
```

### Rate Limiting
```bash
ccb-ratelimit status
ccb-ratelimit set claude --rpm 50
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CCB Platform                                 │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Agent Layer (9 Agents)                    │   │
│  │  Sisyphus │ Oracle │ Librarian │ Explorer │ Frontend        │   │
│  │  Reviewer │ Workflow │ Polyglot │ Autonomous                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Routing Engine                            │   │
│  │  Task Analysis → Provider Selection → Fallback Chain         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                 Provider Layer (9 Providers)                 │   │
│  │  Claude │ Codex │ Gemini │ OpenCode │ DeepSeek              │   │
│  │  Droid │ iFlow │ Kimi │ Qwen                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
~/.local/share/codex-dual/
├── bin/                    # CLI commands
│   ├── ccb-ask, ccb-agent, ccb-ratelimit
│   └── cask, gask, dskask, ...
├── lib/                    # Core modules
│   ├── unified_router.py   # Routing engine
│   ├── agent_registry.py   # Agent definitions
│   ├── agent_executor.py   # Agent execution
│   ├── provider_commands.py # Provider mappings
│   └── agents/             # Agent implementations
├── mcp/                    # MCP servers
└── config/                 # Configuration templates

~/.ccb_config/
├── unified-router.yaml     # Routing rules
├── phase4.yaml             # Advanced features config
└── *.db                    # SQLite databases
```

---

## Contributors

- **Leo** ([@LeoLin990405](https://github.com/LeoLin990405)) - Project Lead
- **Claude** (Anthropic Claude Opus 4.5) - Architecture & Implementation

---

## License

MIT License - See [LICENSE](LICENSE)

---

<p align="center">
  <sub>Built with collaboration between human and AI</sub>
</p>
