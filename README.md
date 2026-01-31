<p align="center">
  <img src="https://img.shields.io/badge/CCB-Multi--AI%20Platform-blue?style=for-the-badge" alt="CCB">
  <img src="https://img.shields.io/badge/Providers-9-green?style=for-the-badge" alt="Providers">
  <img src="https://img.shields.io/badge/Agents-9-orange?style=for-the-badge" alt="Agents">
</p>

<h1 align="center">CCB - Claude Code Bridge</h1>

<p align="center">
  <strong>Enterprise-Grade Multi-AI Orchestration Platform</strong>
  <br>
  <em>Intelligent routing, specialized agents, and unified API for 9 AI providers</em>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-gateway-api">Gateway API</a> •
  <a href="#-agents">Agents</a> •
  <a href="#-installation">Installation</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/WebSocket-010101?logo=socket.io&logoColor=white" alt="WebSocket">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

**English** | [中文](README_zh.md)

---

## 🎯 Overview

**CCB (Claude Code Bridge)** is a production-ready multi-AI orchestration platform that unifies 9 AI providers under a single, intelligent interface. It features automatic task routing, specialized agents for different domains, and a modern Gateway API with WebSocket support.

### Why CCB?

| Challenge | CCB Solution |
|-----------|--------------|
| Multiple AI CLIs with different interfaces | **Unified command interface** for all providers |
| Manual provider selection | **Intelligent routing** based on task analysis |
| No persistence or state management | **SQLite-backed state store** with request queuing |
| Terminal-dependent communication | **REST API + WebSocket** for decoupled architecture |
| Single-provider limitations | **9 specialized agents** with automatic fallback |

---

## ✨ Features

### Core Platform

| Feature | Description |
|---------|-------------|
| **9 AI Providers** | Claude, Codex, Gemini, OpenCode, DeepSeek, Droid, iFlow, Kimi, Qwen |
| **Intelligent Routing** | Task-aware provider selection with keyword and file pattern matching |
| **Magic Keywords** | `@deep`, `@review`, `@all`, `@docs`, `@search` for special behaviors |
| **Unified CLI** | Consistent `*ask` / `*ping` commands across all providers |

### Gateway API (Phase 5)

| Feature | Description |
|---------|-------------|
| **REST API** | `POST /api/ask`, `GET /api/reply/{id}`, `GET /api/status` |
| **WebSocket** | Real-time request/response streaming at `/api/ws` |
| **Priority Queue** | Request prioritization with SQLite persistence |
| **Multi-Backend** | HTTP API, CLI Exec, Terminal integration |
| **Health Monitoring** | Automatic provider health checks and metrics |

### Advanced Capabilities

| Feature | Description |
|---------|-------------|
| **Rate Limiting** | Token bucket algorithm per provider |
| **MCP Aggregation** | Unified tool discovery across MCP servers |
| **OAuth2 Auth** | Secure Web API access |
| **LSP/AST Tools** | Code intelligence with tree-sitter |
| **Batch Processing** | Parallel task execution |
| **Smart Caching** | Reduce redundant API calls |
| **Auto Auth Terminal** | Auto-open terminal for CLI authentication when needed |
| **WezTerm Integration** | TTY-dependent CLIs execute in WezTerm panes |

---

## 🚀 Quick Start

### Basic Usage

```bash
# Smart routing - auto-selects optimal provider
ccb ask "Add a React component"        # → Gemini (frontend)
ccb ask "Design an API endpoint"       # → Codex (backend)
ccb ask "Analyze algorithm complexity" # → DeepSeek (reasoning)

# Magic keywords
ccb ask "@deep analyze this algorithm"   # Force deep reasoning
ccb ask "@review check this code"        # Force code review
ccb ask "@all what's the best approach"  # Multi-provider query

# Direct provider commands
cask "your question"   # Codex
gask "your question"   # Gemini
dskask "your question" # DeepSeek
kask "your question"   # Kimi
qask "your question"   # Qwen
```

### Gateway API

```bash
# Start the gateway server
ccb-gateway start

# Send request via REST API
curl -X POST http://localhost:8765/api/ask \
  -H "Content-Type: application/json" \
  -d '{"provider": "gemini", "message": "Hello"}'

# Get response
curl http://localhost:8765/api/reply/{request_id}

# Check system status
curl http://localhost:8765/api/status
```

### Agent Execution

```bash
# Auto-select best agent for task
ccb-agent auto "implement sorting function"

# Execute with specific agent
ccb-agent execute reviewer "audit this code"
ccb-agent execute oracle "analyze algorithm complexity"

# List available agents
ccb-agent list
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CCB Platform Architecture                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Agent Layer (9 Agents)                         │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──��───────┐ ┌──────────┐    │ │
│  │  │ Sisyphus │ │  Oracle  │ │Librarian │ │ Explorer │ │ Frontend │    │ │
│  │  │  (Code)  │ │(Reasoning│ │  (Docs)  │ │ (Search) │ │  (UI/UX) │    │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘    │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                 │ │
│  │  │ Reviewer │ │ Workflow │ │ Polyglot │ │Autonomous│                 │ │
│  │  │ (Review) │ │  (Auto)  │ │ (i18n)   │ │(Long-run)│                 │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      Gateway API Layer (Phase 5)                       │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │ │
│  │  │  REST API   │ │  WebSocket  │ │Request Queue│ │ State Store │     │ │
│  │  │ (FastAPI)   │ │  (Real-time)│ │ (Priority)  │ │  (SQLite)   │     │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Unified Router Engine                          │ │
│  │         Task Analysis → Provider Selection → Fallback Chain            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                           Backend Layer                                │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                 │ │
│  │  │ HTTP API │ │ CLI Exec │ │ Terminal │ │   FIFO   │                 │ │
│  │  │(Anthropic│ │ (Codex,  │ │ (Legacy) │ │ (Legacy) │                 │ │
│  │  │ DeepSeek)│ │ Gemini)  │ │          │ │          │                 │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      Provider Layer (9 Providers)                      │ │
│  │  ┌───────┐ ┌───────┐ ┌───────┐ ┌────────┐ ┌────────┐                 │ │
│  │  │Claude │ │ Codex │ │Gemini │ │OpenCode│ │DeepSeek│                 │ │
│  │  └───────┘ └───────┘ └───────┘ └────────┘ └────────┘                 │ │
│  │  ┌───────┐ ┌───────┐ ┌───────┐ ┌────────┐                            │ │
│  │  │ Droid │ │ iFlow │ │ Kimi  │ │  Qwen  │                            │ │
│  │  └───────┘ └───────┘ └───────┘ └────────┘                            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 Gateway API

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ask` | Submit a request to a provider |
| `GET` | `/api/reply/{request_id}` | Get response for a request |
| `GET` | `/api/status` | Get gateway and provider status |
| `DELETE` | `/api/request/{request_id}` | Cancel a pending request |
| `GET` | `/docs` | Interactive API documentation |

### Request Example

```bash
# Submit request
curl -X POST http://localhost:8765/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "gemini",
    "message": "Explain async/await in Python",
    "timeout_s": 60,
    "priority": 50
  }'

# Response
{
  "request_id": "abc123-def",
  "provider": "gemini",
  "status": "queued"
}
```

### WebSocket Events

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8765/api/ws');

// Subscribe to events
ws.send(JSON.stringify({
  type: 'subscribe',
  channels: ['requests', 'providers']
}));

// Receive events
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // { type: 'request_update', request_id: '...', status: 'completed', response: '...' }
};
```

### Provider Status

```bash
curl http://localhost:8765/api/status | jq '.providers'
```

```json
[
  {"name": "gemini", "enabled": true, "status": "healthy", "avg_latency_ms": 2500},
  {"name": "codex", "enabled": true, "status": "healthy", "avg_latency_ms": 5800},
  {"name": "deepseek", "enabled": true, "status": "healthy", "avg_latency_ms": 48000},
  {"name": "kimi", "enabled": true, "status": "healthy", "avg_latency_ms": 5000},
  {"name": "qwen", "enabled": true, "status": "healthy", "avg_latency_ms": 11000},
  {"name": "iflow", "enabled": true, "status": "healthy", "avg_latency_ms": 40000},
  {"name": "opencode", "enabled": true, "status": "healthy", "avg_latency_ms": 23000}
]
```

---

## 🤖 Agents

### Agent Overview

| Agent | Purpose | Primary Providers | Keywords |
|-------|---------|-------------------|----------|
| **Sisyphus** | Code implementation | Codex, Gemini | implement, create, build |
| **Oracle** | Deep reasoning & analysis | DeepSeek, Claude | analyze, reason, algorithm |
| **Librarian** | Documentation & search | Claude, Gemini | document, explain |
| **Explorer** | Codebase navigation | Gemini, Claude | find, search, locate |
| **Frontend** | UI/UX development | Gemini, Claude | react, vue, component |
| **Reviewer** | Code review & testing | Gemini, Claude | review, audit, check |
| **Workflow** | Multi-step automation | iFlow, Droid | automate, pipeline |
| **Polyglot** | Translation & i18n | Kimi, Qwen | translate, multilingual |
| **Autonomous** | Long-running tasks | Droid, Codex | background, long-running |

### Agent Commands

```bash
# List all agents with capabilities
ccb-agent list

# Auto-select agent based on task
ccb-agent auto "implement a binary search tree"

# Execute with specific agent
ccb-agent execute sisyphus "create a REST API endpoint"
ccb-agent execute oracle "analyze time complexity of this algorithm"
ccb-agent execute reviewer "review this pull request"

# Show which agent would be selected
ccb-agent match "translate this documentation to Chinese"
```

---

## 📦 Providers

### Provider Matrix

| Provider | Command | Backend | Best For | Status |
|----------|---------|---------|----------|--------|
| **Claude** | `lask` | HTTP API | Architecture, general | ✅ |
| **Codex** | `cask` | CLI (`exec --json`) | Backend, API | ✅ |
| **Gemini** | `gask` | CLI + WezTerm¹ | Frontend, review | ✅ |
| **OpenCode** | `oask` | CLI (`run --format json`) | General coding | ✅ |
| **DeepSeek** | `dskask` | CLI (`-q`) | Deep reasoning | ✅ |
| **Droid** | `dask` | Terminal | Autonomous | ⚠️ |
| **iFlow** | `iask` | CLI (`-p`) | Workflow | ✅ |
| **Kimi** | `kask` | CLI (`--quiet -p`) | Chinese, long context | ✅ |
| **Qwen** | `qask` | CLI | Multilingual | ✅ |

¹ Gemini CLI requires TTY environment; Gateway uses WezTerm pane execution for proper TTY support.

### Routing Rules

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
| `@deep` | Deep reasoning | Force DeepSeek provider |
| `@review` | Code review | Force Gemini review mode |
| `@docs` | Documentation | Query Context7 |
| `@search` | Web search | Trigger web search |
| `@all` | Multi-provider | Query multiple providers |

---

## 📁 Project Structure

```
~/.local/share/codex-dual/
├── bin/                        # CLI commands
│   ├── ccb-ask                 # Smart routing command
│   ├── ccb-agent               # Agent execution
│   ├── ccb-gateway             # Gateway management
│   ├── ccb-ratelimit           # Rate limiting
│   └── cask, gask, dskask...   # Provider-specific commands
│
├── lib/                        # Core modules
│   ├── unified_router.py       # Intelligent routing engine
│   ├── agent_registry.py       # Agent definitions
│   ├── agent_executor.py       # Agent execution logic
│   ├── provider_commands.py    # Provider command mappings
│   │
│   └── gateway/                # Gateway API module (Phase 5)
│       ├── gateway_server.py   # FastAPI server
│       ├── gateway_api.py      # REST endpoints
│       ├── gateway_config.py   # Configuration management
│       ├── state_store.py      # SQLite state persistence
│       ├── request_queue.py    # Priority queue
│       ├── monitor.py          # Real-time monitoring
│       ├── models.py           # Data models
│       └── backends/           # Backend implementations
│           ├── base_backend.py
│           ├── http_backend.py
│           ├── cli_backend.py
│           └── terminal_backend.py
│
├── mcp/                        # MCP servers
├── config/                     # Configuration templates
│   └── gateway.yaml            # Gateway configuration
│
└── install.sh                  # Installation script

~/.ccb_config/                  # User configuration
├── unified-router.yaml         # Routing rules
├── phase4.yaml                 # Advanced features
└── gateway.db                  # Gateway state database
```

---

## 🔧 Installation

### Prerequisites

- **Python 3.9+**
- **WezTerm** or **tmux** (for terminal multiplexing)
- Provider CLIs: `claude`, `codex`, `gemini`, `opencode`, `deepseek`, `kimi`, `qwen`

### Install

```bash
# Clone repository
git clone https://github.com/LeoLin990405/ccb.git ~/.local/share/codex-dual

# Run installation
cd ~/.local/share/codex-dual && ./install.sh

# Add to PATH (add to ~/.zshrc or ~/.bashrc)
export PATH="$HOME/.local/share/codex-dual/bin:$PATH"
```

### Environment Variables

```bash
# Add to ~/.zshrc or ~/.bashrc
export CCB_SIDECAR_AUTOSTART=1      # Auto-start sidecar panes
export CCB_SIDECAR_DIRECTION=right  # Sidecar pane direction
export CCB_CLI_READY_WAIT_S=20      # CLI ready timeout
export CCB_USE_GATEWAY=1            # Enable Gateway mode
export CCB_GATEWAY_PORT=8765        # Gateway port
export CCB_AUTO_OPEN_AUTH=1         # Auto-open auth terminal on timeout (default: 1)
export CCB_DEBUG=1                  # Enable verbose debug logging
```

### Verify Installation

```bash
# Check CCB version
ccb --version

# Check provider health
ccb health

# Start gateway
ccb-gateway start

# Test routing
ccb route "implement a React component"
```

---

## 📊 Performance

### Gateway Metrics

| Metric | Description |
|--------|-------------|
| `total_requests` | Total requests processed |
| `active_requests` | Currently processing |
| `queue_depth` | Pending requests |
| `avg_latency_ms` | Average response time |
| `success_rate` | Request success rate |

### Provider Latency (Typical)

| Provider | Avg Latency | Use Case |
|----------|-------------|----------|
| Gemini | ~2.5s | Fast responses |
| Codex | ~5.8s | Code generation |
| Kimi | ~5.0s | Chinese content |
| Qwen | ~11s | Multilingual |
| OpenCode | ~23s | General coding |
| iFlow | ~40s | Workflow automation |
| DeepSeek | ~48s | Deep reasoning |

---

## 🙏 Acknowledgements

This project stands on the shoulders of giants:

- **[bfly123/claude_code_bridge](https://github.com/bfly123/claude_code_bridge)** - Original multi-AI collaboration framework
- **[Grafbase/Nexus](https://github.com/grafbase/nexus)** - AI gateway architecture inspiration
- **[code-yeongyu/oh-my-opencode](https://github.com/code-yeongyu/oh-my-opencode)** - Agent orchestration patterns

---

## 👥 Contributors

- **Leo** ([@LeoLin990405](https://github.com/LeoLin990405)) - Project Lead
- **Claude** (Anthropic Claude Opus 4.5) - Architecture & Implementation

---

## 📄 License

MIT License - See [LICENSE](LICENSE)

---

<p align="center">
  <sub>Built with collaboration between human and AI</sub>
  <br>
  <sub>⭐ Star this repo if you find it useful!</sub>
</p>
