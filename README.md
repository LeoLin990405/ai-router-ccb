<div align="center">

# 🤖 CCB Gateway

### Enterprise-Grade Multi-AI Orchestration Platform

[![Stars](https://img.shields.io/github/stars/LeoLin990405/ai-router-ccb?style=social)](https://github.com/LeoLin990405/ai-router-ccb)
[![License](https://img.shields.io/github/license/LeoLin990405/ai-router-ccb?color=blue)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Version](https://img.shields.io/badge/version-0.19--alpha-brightgreen)](https://github.com/LeoLin990405/ai-router-ccb/releases)

**Claude orchestrates 8 AI providers through unified Gateway API with automatic memory injection and real-time monitoring**

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Architecture](#-architecture) • [API](#-api-reference)

[🇺🇸 English](README.md) | [🇨🇳 简体中文](README.zh-CN.md)

<img src="screenshots/webui-demo.gif" alt="CCB Gateway Demo" width="800">

</div>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Why CCB Gateway?](#-why-ccb-gateway)
- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Usage](#-usage)
- [Memory System](#-memory-system-v018)
- [Skills Discovery](#-skills-discovery-v019)
- [Multi-AI Discussion](#-multi-ai-discussion)
- [Web UI](#-web-ui)
- [API Reference](#-api-reference)
- [Documentation](#-documentation)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Overview

**CCB Gateway** is a production-ready multi-AI orchestration platform where **Claude acts as the intelligent orchestrator**, routing tasks to 8 specialized AI providers through a unified Gateway API with automatic memory, caching, retry, and real-time monitoring.

**What makes it unique:**
- 🧠 **Automatic Memory** - Every conversation remembered, relevant context auto-injected
- 🎯 **Pre-loaded Context** - 53 Skills + 8 Providers + 4 MCP Servers embedded in every request
- 🔍 **Skills Discovery** - Auto-find and recommend relevant skills via Vercel Skills CLI
- ⚡ **Intelligent Routing** - Speed-tiered fallback with smart provider selection
- 📊 **Real-time Monitoring** - WebSocket-based dashboard with live metrics
- 🔄 **Multi-AI Discussion** - Collaborative problem-solving across multiple AIs
- ☁️ **Cloud Sync** - Google Drive backup with hourly auto-sync

```
                    ┌─────────────────────────────┐
                    │   Claude (Orchestrator)     │
                    │      Claude Code CLI        │
                    └─────────────┬───────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
    ┌─────────▼─────────┐ ┌──────▼──────┐ ┌─────────▼─────────┐
    │   ccb-cli         │ │ Gateway API │ │   Web UI          │
    │  Direct Call      │ │  REST/WS    │ │   Dashboard       │
    └─────────┬─────────┘ └──────┬──────┘ └─────────┬─────────┘
              │                  │                   │
              └──────────────────┼───────────────────┘
                                 │
          ┌──────────┬───────────┼───────────┬───────────┬─────────┐
          ▼          ▼           ▼           ▼           ▼         ▼
     ┌────────┐ ┌────────┐ ┌─────────┐ ┌────────┐ ┌────────┐ ┌────────┐
     │ Kimi   │ │ Qwen   │ │DeepSeek │ │ Codex  │ │Gemini  │ │ iFlow  │
     │ 🚀 7s  │ │ 🚀 12s │ │ ⚡ 16s  │ │ 🐢 48s │ │ 🐢 71s │ │ ⚡ 25s │
     └────────┘ └────────┘ └─────────┘ └────────┘ └────────┘ └────────┘
                           ┌─────────┐ ┌─────────┐
                           │ Qoder   │ │OpenCode │
                           │ ⚡ 30s  │ │ ⚡ 42s  │
                           └─────────┘ └─────────┘
```

---

## 💡 Why CCB Gateway?

<table>
<tr>
<td width="50%">

### The Problem

❌ Multiple AI CLIs with different interfaces
❌ Manual provider selection is tedious
❌ No memory between conversations
❌ Context lost, AI doesn't know available tools
❌ No visibility into operations
❌ No collaboration between AIs
❌ Wasted time on failed requests

</td>
<td width="50%">

### The Solution

✅ **Unified Gateway API** - One interface for all
✅ **Intelligent Routing** - Auto-select best AI
✅ **Automatic Memory** - Context preserved
✅ **Pre-loaded Tools** - 53 Skills embedded
✅ **Real-time Dashboard** - Full visibility
✅ **Multi-AI Discussion** - Collaborative AI
✅ **Retry & Fallback** - Built-in resilience

</td>
</tr>
</table>

---

## ✨ Features

### 🧠 Automatic Memory System (v0.18)

**Zero-configuration memory** - Every conversation is remembered and relevant context is automatically injected.

<details>
<summary><b>Pre-loaded Context (Click to expand)</b></summary>

Every request automatically includes:
- 🎯 **53 Claude Code Skills** - frontend-design, pdf, xlsx, pptx, ccb, lenny-*, etc.
- 🔌 **4 MCP Servers** - chroma-mcp, playwright-mcp, etc.
- 🤖 **8 AI Providers** - Models, strengths, use cases
- 💭 **Relevant Memories** - Past conversations retrieved via FTS5 full-text search

**Performance:**
- ⚡ <100ms overhead per request (<5% impact)
- 📝 100% conversation capture rate
- 🔍 ~80% search accuracy (90%+ with future vector search)

</details>

<details>
<summary><b>Memory Backend</b></summary>

- 💾 **SQLite Storage** - All conversations in `~/.ccb/ccb_memory.db`
- 🔎 **Full-text Search** - FTS5 with Chinese support
- ☁️ **Cloud Sync** - Google Drive backup (hourly auto-sync)
- 📊 **Analytics** - Track which AI excels at which tasks

</details>

<details>
<summary><b>Automatic Integration</b></summary>

**Pre-Request Hook:**
```python
# Before calling AI provider
request = await memory_middleware.pre_request(request)
# Result: Message enhanced with system context + relevant memories
```

**Post-Response Hook:**
```python
# After AI responds
await memory_middleware.post_response(request, response)
# Result: Conversation saved to database automatically
```

</details>

**Usage:**
```bash
# No special command needed - ccb-cli now has automatic memory!
ccb-cli kimi "How do I build a login page?"

# [Gateway Middleware]
#   ✓ System context injected (53 Skills + 4 MCP + 8 Providers)
#   ✓ 2 relevant memories injected
#
# Response: Based on our previous discussion about React...
#
# 💡 [2 relevant memories auto-injected]

# View memories
python3 lib/memory/memory_lite.py recent 10
python3 lib/memory/memory_lite.py search "React"
```

---

### ⚡ Intelligent Routing & Fallback

**Speed-tiered provider chains** with automatic fallback on failure:

```yaml
Fast Tier (3-15s):    Kimi → Qwen → DeepSeek
Medium Tier (15-45s): iFlow → Qoder → OpenCode
Slow Tier (45-90s):   Codex → Gemini
```

**Features:**
- 🎯 Smart provider recommendation based on task keywords
- 🔄 Automatic retry with exponential backoff
- 📉 Fallback chains for resilience
- ⚖️ Load balancing across providers

---

### 🤝 Multi-AI Discussion

**Collaborative problem-solving** - Multiple AIs discuss and reach consensus:

```bash
# Start a discussion with 3 AIs
ccb-submit discuss \
  --providers kimi,codex,gemini \
  --rounds 3 \
  --strategy "consensus" \
  "Design a scalable microservices architecture"

# Each AI:
# Round 1: Proposes initial solution
# Round 2: Reviews others' proposals
# Round 3: Final recommendation

# Output: Synthesized solution from all perspectives
```

**Use cases:**
- 🏗️ Architecture design
- 🐛 Complex debugging
- 📝 Technical documentation
- 💡 Brainstorming sessions

---

### 📊 Real-time Monitoring

**WebSocket-based dashboard** with live updates:

<table>
<tr>
<td width="33%">

**Metrics**
- Request count
- Success rate
- Avg latency
- Provider status

</td>
<td width="33%">

**Queue**
- Pending requests
- Processing
- Completed
- Failed

</td>
<td width="33%">

**Logs**
- Real-time events
- Error tracking
- Performance data
- WebSocket feed

</td>
</tr>
</table>

Access at: http://localhost:8765/web

---

### 🚀 Production Features

<table>
<tr>
<td width="50%">

**Performance**
- ⚡ Response caching (configurable TTL)
- 🔄 Request retry with backoff
- 📊 Rate limiting per provider
- 🎯 Parallel execution

</td>
<td width="50%">

**Reliability**
- 🛡️ Automatic fallback chains
- 💾 Persistent request queue
- 📝 Comprehensive logging
- 🔍 Request tracking (ID-based)

</td>
</tr>
<tr>
<td width="50%">

**Security**
- 🔐 API key authentication
- 🚦 Rate limiting
- 🔒 Secure credential storage
- 📋 Audit logging

</td>
<td width="50%">

**Observability**
- 📊 Prometheus metrics
- 📈 Real-time dashboards
- 🔔 WebSocket events
- 📋 Detailed request logs

</td>
</tr>
</table>

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      CCB Gateway (v0.18)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │            Memory Middleware (v0.18)                    │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │  Pre-Request Hook:                                      │    │
│  │  • SystemContextBuilder (53 Skills + 4 MCP + 8 Prov)   │    │
│  │  • MemoryLite.search() → FTS5 search                   │    │
│  │  • Provider recommendation                              │    │
│  │  • Context injection                                    │    │
│  │                                                          │    │
│  │  Post-Response Hook:                                    │    │
│  │  • MemoryLite.record() → SQLite                        │    │
│  │  • Update statistics                                    │    │
│  └────────────────────────────────────────────────────────┘    │
│                          │                                       │
│  ┌────────────────────────▼─────────────────────────────┐      │
│  │            Gateway Server Core                        │      │
│  ├───────────────────────────────────────────────────────┤      │
│  │  • Request Queue (async)                              │      │
│  │  • Retry Executor                                     │      │
│  │  • Cache Manager                                      │      │
│  │  • Rate Limiter                                       │      │
│  │  • Metrics Collector                                  │      │
│  └───────────────────────────────────────────────────────┘      │
│                          │                                       │
│  ┌───────────┬───────────┼───────────┬───────────┐            │
│  ▼           ▼           ▼           ▼           ▼            │
│ ┌─────┐   ┌─────┐   ┌─────────┐  ┌─────┐   ┌───────┐        │
│ │Kimi │   │Qwen │   │DeepSeek │  │Codex│   │Gemini │   ...  │
│ └─────┘   └─────┘   └─────────┘  └─────┘   └───────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Memory System Flow

```
User Request
    │
    ├─→ [Memory Middleware: Pre-Request]
    │   ├─→ Extract keywords from message
    │   ├─→ SystemContextBuilder.get_relevant_context()
    │   │   ├─→ Filter 53 Skills by keywords
    │   │   ├─→ Get current Provider info
    │   │   └─→ Get active MCP Servers
    │   ├─→ MemoryLite.search_conversations()
    │   │   └─→ SQLite FTS5 full-text search
    │   └─→ Inject to prompt:
    │       """
    │       # System Context
    │       ## 🤖 Current Provider: kimi
    │       ## 🛠️ Relevant Skills: frontend-design, pptx
    │       ## 💭 Relevant Memories: [previous conversation]
    │
    │       ---
    │       # User Request
    │       [original message]
    │       """
    │
    ├─→ [Provider Call]
    │   └─→ Enhanced message → AI Provider
    │
    └─→ [Memory Middleware: Post-Response]
        ├─→ Record conversation to SQLite
        ├─→ Update FTS5 index
        └─→ Update provider statistics
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Node.js 16+ (for MCP servers)
- Git

### Installation

```bash
# 1. Clone repository
git clone https://github.com/LeoLin990405/ai-router-ccb.git
cd ai-router-ccb

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install Node.js dependencies (for MCP)
npm install

# 4. Configure AI providers
# Edit config files in ~/.claude/ or use environment variables
```

### Start Gateway Server

```bash
# Start with default config
python3 -m lib.gateway.gateway_server --port 8765

# With custom config
python3 -m lib.gateway.gateway_server --config config/gateway.yaml

# Output:
# [SystemContext] Preloading system information...
# [SystemContext] Loaded 53 skills
# [SystemContext] Loaded 8 providers
# [SystemContext] Loaded 4 MCP servers
# [MemoryMiddleware] Initialized (enabled=True)
# [GatewayServer] Memory Middleware initialized successfully
# ✓ Server running at http://localhost:8765
```

### First Request

```bash
# Using ccb-cli (automatic memory!)
ccb-cli kimi "Explain React hooks"

# Using curl
curl -X POST http://localhost:8765/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "kimi",
    "message": "Explain React hooks",
    "wait": true,
    "timeout": 60
  }'

# Response includes:
# - AI response
# - Metadata about injected context
# - Latency metrics
```

---

## 📚 Usage

### ccb-cli - Direct CLI

**Fastest way to call any AI provider:**

```bash
# Basic usage
ccb-cli <provider> [model] "<message>"

# Examples
ccb-cli kimi "How do I optimize SQL queries?"
ccb-cli codex o3 "Prove the halting problem is undecidable"
ccb-cli gemini 3f "Design a responsive navbar"
ccb-cli qwen "Analyze this dataframe"

# With agent role
ccb-cli codex o3 -a reviewer "Review this PR"
ccb-cli kimi -a sisyphus "Fix this bug: ..."
```

**Model shortcuts:**
| Provider | Shortcuts | Example |
|----------|-----------|---------|
| codex | o3, o4-mini, gpt-4o, o1-pro | `ccb-cli codex o3 "..."` |
| gemini | 3f, 3p, 2.5f, 2.5p | `ccb-cli gemini 3f "..."` |
| kimi | thinking, normal | `ccb-cli kimi thinking "..."` |
| deepseek | reasoner, chat | `ccb-cli deepseek reasoner "..."` |

---

### Gateway API

**RESTful API with WebSocket support:**

#### POST /api/ask (Synchronous)

```bash
curl -X POST http://localhost:8765/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "kimi",
    "message": "Your question",
    "wait": true,
    "timeout": 120
  }'

# Response:
{
  "status": "completed",
  "response": "AI response here...",
  "provider": "kimi",
  "latency_ms": 8500,
  "metadata": {
    "_memory_injected": true,
    "_memory_count": 2,
    "_system_context_injected": true
  }
}
```

#### POST /api/submit (Asynchronous)

```bash
# Submit request
curl -X POST http://localhost:8765/api/submit \
  -d '{"provider": "kimi", "message": "Your question"}'

# Returns: {"request_id": "abc123", "status": "queued"}

# Query result
curl http://localhost:8765/api/query/abc123

# Response:
{
  "request_id": "abc123",
  "status": "completed",
  "response": "AI response...",
  "latency_ms": 8500
}
```

#### WebSocket /ws

```javascript
const ws = new WebSocket('ws://localhost:8765/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === "request_processing") {
    console.log(`Processing: ${data.data.request_id}`);
  } else if (data.type === "request_completed") {
    console.log(`Completed: ${data.data.request_id}`);
  }
};
```

---

## 🧠 Memory System (v0.18)

### Architecture

The memory system consists of three layers:

1. **System Context Builder** - Pre-loads Skills/MCP/Providers at startup
2. **Memory Middleware** - Injects context and records conversations
3. **Memory Backend** - SQLite database with FTS5 search

### Database Schema

```sql
-- conversations table
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    provider TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    metadata TEXT,  -- JSON
    tokens INTEGER DEFAULT 0
);

-- FTS5 full-text search index
CREATE VIRTUAL TABLE conversations_fts USING fts5(
    question, answer, provider,
    content='conversations',
    content_rowid='id'
);
```

### CLI Commands

```bash
# View recent conversations
python3 lib/memory/memory_lite.py recent 10

# Search conversations
python3 lib/memory/memory_lite.py search "React hooks"

# View statistics
python3 lib/memory/memory_lite.py stats

# Cloud sync
ccb-sync push    # Push to Google Drive
ccb-sync pull    # Pull from Google Drive
ccb-sync status  # Check sync status
```

### Configuration

**`~/.ccb/gateway_config.json`:**
```json
{
  "memory": {
    "enabled": true,
    "auto_inject": true,
    "auto_record": true,
    "inject_system_context": true,
    "max_injected_memories": 5
  },
  "recommendation": {
    "enabled": true,
    "auto_switch_provider": false
  }
}
```

---

## 🔍 Skills Discovery (v0.19)

**Auto-discover and recommend relevant Claude Code Skills** - Integrates with [Vercel Skills](https://github.com/vercel-labs/skills) to find and install skills on-demand.

### How It Works

```
User Request → Extract Keywords → Search Skills (Local + Remote)
                                         ↓
                        ┌────────────────┴────────────────┐
                        │                                  │
                   scan-skills.sh              npx skills find [query]
                   (Local Skills)               (Vercel Registry)
                        │                                  │
                        └────────────────┬────────────────┘
                                         ↓
                              Rank by Relevance Score
                              (Keywords + Usage History)
                                         ↓
                         Inject Recommendations to Context
                                         ↓
                            AI Sees Available Skills
                                         ↓
                          Record Usage → Learn & Improve
```

### Features

- 🔍 **Local + Remote Search** - Scans installed skills and searches Vercel Skills registry
- 🧠 **Learning Algorithm** - Recommendations improve based on usage history
- 📊 **Relevance Scoring** - Keywords + historical usage + installation status
- 🚀 **Auto-Installation** - Optionally auto-install recommended remote skills
- 💾 **Cached Results** - Skills cached in memory database for fast access

### Usage

**Automatic (via Gateway):**
```bash
# Gateway automatically discovers relevant skills
ccb-cli kimi "help me test React components"

# Gateway output:
# [MemoryMiddleware] 💡 发现 2 个相关 Skill: /webapp-testing, jest-react-testing
```

**Manual Search:**
```bash
# Find skills for a specific task
ccb-skills recommend "create PDF"

# Output:
# 💡 发现 1 个相关 Skill: /pdf
#
#   pdf (score: 23, installed: ✓)
#     Comprehensive PDF manipulation toolkit
#     Usage: /pdf

# View usage statistics
ccb-skills stats

# Refresh cache
ccb-skills scan
```

### Configuration

```json
{
  "skills": {
    "auto_discover": true,        // Auto-find skills
    "recommend_skills": true,     // Show recommendations
    "max_recommendations": 3,     // Max skills to recommend
    "auto_install": false,        // Auto-install remote skills
    "cache_ttl_hours": 24         // Cache expiration
  }
}
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `ccb-skills scan` | Refresh local skills cache |
| `ccb-skills recommend "<task>"` | Get skill recommendations |
| `ccb-skills match "<task>"` | Find matching skills (detailed) |
| `ccb-skills stats` | Show usage statistics |
| `ccb-skills list [--installed]` | List all/installed skills |

### Relevance Algorithm

```python
score = 0

# Name match (highest priority)
if keyword in skill_name: score += 10

# Description match
if keyword in description: score += 5

# Trigger match
if keyword in triggers: score += 3

# Installed bonus
if installed: score += 2

# Usage history boost (capped at +5 per keyword)
score += min(usage_count, 5)
```

### Example: Automatic Discovery

```bash
# User request
$ ccb-cli kimi "create an Excel spreadsheet"

# Behind the scenes:
[MemoryMiddleware] Extracted keywords: ['create', 'excel', 'spreadsheet']
[SkillsDiscovery] Searching local skills...
[SkillsDiscovery] Found: xlsx (score: 20)
[SkillsDiscovery] Searching remote skills: npx skills find excel
[SkillsDiscovery] Found: excel-toolkit (score: 15)
[MemoryMiddleware] 💡 发现 2 个相关 Skill: /xlsx, excel-toolkit

# AI sees in context:
## 🛠️ 相关技能推荐
- **/xlsx** (score: 20) - Comprehensive spreadsheet toolkit
  ✓ 已安装，可直接使用: `/xlsx`
- **excel-toolkit** (score: 15) - Excel automation from Vercel
  📦 可安装: npx skills add vercel-labs/agent-skills@excel-toolkit -g -y

# Result: AI uses /xlsx skill automatically
```

---

## 💬 Multi-AI Discussion

**Collaborative problem-solving across multiple AIs:**

### Basic Discussion

```bash
ccb-submit discuss \
  --providers kimi,codex,gemini \
  --rounds 3 \
  --strategy consensus \
  "Design a distributed cache system"
```

### Aggregation Strategies

- **consensus** - All AIs must agree
- **majority** - Most common answer wins
- **first_success** - First valid response
- **best_quality** - Highest quality (scored)

### Use Cases

```bash
# Architecture design
ccb-submit discuss -p kimi,codex,gemini -r 3 \
  "Design microservices for e-commerce"

# Code review
ccb-submit discuss -p codex,deepseek -r 2 \
  "Review this implementation: [code]"

# Brainstorming
ccb-submit discuss -p kimi,gemini,iflow -r 3 \
  "Ideas for improving user onboarding"
```

---

## 🖥️ Web UI

**Real-time monitoring dashboard at http://localhost:8765/web**

### Features

- 📊 **Live Metrics** - Request count, success rate, latency
- 📋 **Request Queue** - Pending, processing, completed
- 🔴 **Live Logs** - Real-time event stream via WebSocket
- 🤖 **Provider Status** - Health checks for all providers
- 📈 **Charts** - Performance trends and analytics

### Screenshots

<details>
<summary><b>Dashboard Overview</b></summary>

<img src="screenshots/dashboard.png" alt="Dashboard" width="700">

</details>

<details>
<summary><b>Request Queue</b></summary>

<img src="screenshots/queue.png" alt="Queue" width="700">

</details>

---

## 📖 API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/providers` | List all providers |
| POST | `/api/ask` | Synchronous request |
| POST | `/api/submit` | Asynchronous request |
| GET | `/api/query/{id}` | Query request status |
| GET | `/api/pending` | List pending requests |
| POST | `/api/cancel/{id}` | Cancel request |
| WS | `/ws` | WebSocket connection |

### Request Parameters

**POST /api/ask & /api/submit:**
```json
{
  "provider": "kimi",           // Required: AI provider name
  "message": "Your question",   // Required: User message
  "model": "thinking",          // Optional: Specific model
  "wait": true,                 // Optional: Wait for completion (ask only)
  "timeout": 120,               // Optional: Timeout in seconds
  "metadata": {}                // Optional: Custom metadata
}
```

### Response Format

```json
{
  "request_id": "abc123",
  "status": "completed",         // queued, processing, completed, failed
  "response": "AI response...",  // Only if completed
  "provider": "kimi",
  "latency_ms": 8500,
  "tokens_used": 150,
  "metadata": {
    "_memory_injected": true,
    "_memory_count": 2,
    "_system_context_injected": true
  },
  "error": null                  // Error message if failed
}
```

---

## 📚 Documentation

### Core Documentation

- **[Memory System Architecture](lib/memory/INTEGRATION_DESIGN.md)** - Full design with 4-system analysis
- **[Integration Report](lib/memory/INTEGRATION_REPORT.md)** - Complete implementation report
- **[Database Structure](lib/memory/DATABASE_STRUCTURE.md)** - Schema and queries
- **[Cloud Sync Guide](lib/memory/SYNC_QUICKSTART.md)** - Google Drive setup

### Additional Resources

- **[API Documentation](docs/API.md)** - Complete API reference
- **[Configuration Guide](docs/CONFIG.md)** - All configuration options
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment
- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute

---

## 🗺️ Roadmap

### v0.19 (Q2 2026) - Skills Discovery ✅

- [x] **Skills Discovery Service** - Auto-find and recommend skills
- [x] **Vercel Skills Integration** - Search remote skills via `npx skills find`
- [x] **Learning Algorithm** - Improve recommendations based on usage
- [x] **Memory Integration** - Skills cached and tracked in memory DB
- [ ] Semantic similarity search for skills
- [ ] Auto-install popular skills

### v0.20 (Q3 2026) - Semantic Enhancement

- [ ] Qdrant vector database integration
- [ ] Semantic similarity search for conversations
- [ ] LLM-driven fact extraction
- [ ] Multi-language embeddings

### v0.21 (Q4 2026) - Agent Autonomy

- [ ] Agent memory function calls (Letta mode)
- [ ] Structured memory blocks (core_memory)
- [ ] Self-updating agents
- [ ] Memory version control

### v0.22 (Q4 2026) - Team Collaboration

- [ ] Multi-user memory isolation
- [ ] Shared memory pools
- [ ] Permission system
- [ ] Real-time collaboration

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

### Quick Start for Contributors

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/ai-router-ccb.git
cd ai-router-ccb

# 2. Create branch
git checkout -b feature/your-feature

# 3. Make changes and test
python3 -m pytest tests/

# 4. Commit and push
git commit -m "feat: add your feature"
git push origin feature/your-feature

# 5. Create Pull Request
```

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run linter
flake8 lib/ tests/

# Run type checker
mypy lib/
```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

**Inspired by:**
- [Mem0](https://github.com/mem0ai/mem0) - Semantic memory architecture
- [Letta (MemGPT)](https://github.com/cpacker/MemGPT) - Structured memory blocks
- [LangChain](https://github.com/langchain-ai/langchain) - Memory patterns
- [claude-mem](https://github.com/thedotmack/claude-mem) - Lifecycle hooks

**Built with:**
- [FastAPI](https://fastapi.tiangolo.com) - Modern web framework
- [SQLite](https://www.sqlite.org) - Reliable database
- [Claude Code](https://www.anthropic.com/claude) - AI orchestrator

---

## 📞 Support

- 📧 Email: [your-email@example.com]
- 💬 Discord: [Join our community]
- 🐛 Issues: [GitHub Issues](https://github.com/LeoLin990405/ai-router-ccb/issues)
- 📖 Docs: [Full Documentation](https://your-docs-site.com)

---

<div align="center">

**Made with ❤️ by the CCB Team**

**[⬆ Back to Top](#-ccb-gateway)**

</div>
