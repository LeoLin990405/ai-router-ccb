<p align="center">
  <img src="https://img.shields.io/badge/AI%20Orchestrator-Multi--AI%20Platform-blue?style=for-the-badge" alt="AI Orchestrator">
  <img src="https://img.shields.io/badge/Providers-7-green?style=for-the-badge" alt="Providers">
  <img src="https://img.shields.io/badge/Gateway-REST%20%2B%20WebSocket-orange?style=for-the-badge" alt="Gateway">
</p>

<h1 align="center">AI Orchestrator</h1>

<p align="center">
  <strong>Enterprise-Grade Multi-AI Orchestration Platform</strong>
  <br>
  <em>Unified Gateway API with Claude as orchestrator, managing 7 AI providers</em>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-gateway-api">Gateway API</a> •
  <a href="#-phase-7-features">Phase 7</a> •
  <a href="#-installation">Installation</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Prometheus-E6522C?logo=prometheus&logoColor=white" alt="Prometheus">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

**English** | [中文](README_zh.md)

---

## 🎯 Overview

**AI Orchestrator** is a production-ready multi-AI orchestration platform where **Claude serves as the orchestrator (主脑)**, intelligently dispatching tasks to 7 AI providers through a unified Gateway API.

### Architecture Philosophy

```
┌─────────────────────────────────────────────────────────┐
│              Claude (Orchestrator / 主脑)                │
│                   Claude Code CLI                        │
└─────────────────────┬───────────────────────────────────┘
                      │ Dispatches tasks
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   CCB Gateway API                        │
│                 http://localhost:8765                    │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │ Gemini  │  │ DeepSeek│  │  Codex  │
   └─────────┘  └─────────┘  └─────────┘
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │OpenCode │  │  Kimi   │  │  Qwen   │
   └─────────┘  └─────────┘  └─────────┘
   ┌─────────┐
   │  iFlow  │
   └─────────┘
```

### Why AI Orchestrator?

| Challenge | Solution |
|-----------|----------|
| Multiple AI CLIs with different interfaces | **Unified Gateway API** for all providers |
| Manual provider selection | **Intelligent routing** based on task analysis |
| No visibility into AI operations | **Real-time Monitor** with WebSocket events |
| No caching or retry logic | **Built-in caching, retry, and fallback** |
| No rate limiting or auth | **API key auth + token bucket rate limiting** |

---

## ✨ Features

### Gateway API (Core)

| Feature | Description |
|---------|-------------|
| **REST API** | `POST /api/ask`, `GET /api/reply/{id}`, `GET /api/status` |
| **WebSocket** | Real-time events at `/api/ws` |
| **Priority Queue** | Request prioritization with SQLite persistence |
| **Multi-Backend** | HTTP API, CLI Exec, WezTerm integration |
| **Health Monitoring** | Automatic provider health checks and metrics |

### Phase 7 Production Features

| Feature | Description |
|---------|-------------|
| **API Authentication** | API key-based auth with SHA-256 hashing |
| **Rate Limiting** | Token bucket algorithm, per-key limits |
| **Response Caching** | SQLite-based cache with TTL and pattern exclusion |
| **Retry & Fallback** | Exponential backoff, automatic provider fallback |
| **Parallel Queries** | Query multiple providers simultaneously |
| **Prometheus Metrics** | `/metrics` endpoint for monitoring |
| **Streaming** | Server-Sent Events for real-time responses |

---

## 🚀 Quick Start

### Start Gateway

```bash
# Start the gateway server
cd ~/.local/share/codex-dual
python3 -m lib.gateway.gateway_server --config ~/.ccb/gateway.yaml

# Or use shell functions
source ~/.ccb/gateway-functions.sh
gw-start
```

### Send Requests

```bash
# Via REST API
curl -X POST http://localhost:8765/api/ask \
  -H "Content-Type: application/json" \
  -d '{"provider": "qwen", "message": "Hello"}'

# Get response
curl http://localhost:8765/api/reply/{request_id}?wait=true

# Via shell functions
source ~/.ccb/gateway-functions.sh
gw-ask qwen "your question"
gw-kimi "your question"
gw-parallel "query all providers" first_success
```

### Check Status

```bash
# Gateway status
curl http://localhost:8765/api/status

# Cache stats
curl http://localhost:8765/api/cache/stats

# Prometheus metrics
curl http://localhost:8765/metrics
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AI Orchestrator Architecture                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Claude (Orchestrator / 主脑)                        │ │
│  │              Intelligent task dispatch and coordination                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Gateway API Layer                              │ │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐ │ │
│  │  │ REST API  │ │ WebSocket │ │   Auth    │ │Rate Limit │ │ Metrics │ │ │
│  │  │ (FastAPI) │ │ (Events)  │ │ (API Key) │ │(Tok Bucket│ │(Prometh)│ │ │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └─────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      Processing Layer                                  │ │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐             │ │
│  │  │   Cache   │ │   Retry   │ │  Parallel │ │ Streaming │             │ │
│  │  │ (SQLite)  │ │ (Fallback)│ │ (Multi-AI)│ │   (SSE)   │             │ │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘             │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      Provider Layer (7 Providers)                      │ │
│  │  ┌───────┐ ┌───────┐ ┌────────┐ ┌────────┐ ┌───────┐ ┌───────┐      │ │
│  │  │Gemini │ │DeepSeek│ │ Codex │ │OpenCode│ │ Kimi  │ │ Qwen  │      │ │
│  │  └───────┘ └───────┘ └────────┘ └────────┘ └───────┘ └───────┘      │ │
│  │  ┌───────┐                                                           │ │
│  │  │ iFlow │                                                           │ │
│  │  └───────┘                                                           │ │
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
| `GET` | `/api/reply/{request_id}` | Get response (supports `?wait=true`) |
| `GET` | `/api/status` | Get gateway and provider status |
| `GET` | `/api/requests` | List recent requests |
| `DELETE` | `/api/request/{request_id}` | Cancel a pending request |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/cache/stats` | Cache statistics |
| `DELETE` | `/api/cache` | Clear cache |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/docs` | Interactive API documentation |

### Request Example

```bash
# Submit request
curl -X POST http://localhost:8765/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "qwen",
    "message": "Explain async/await in Python",
    "timeout_s": 60,
    "priority": 50
  }'

# Response
{
  "request_id": "abc123-def",
  "provider": "qwen",
  "status": "queued",
  "cached": false,
  "parallel": false
}

# Parallel query to all providers
curl -X POST http://localhost:8765/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "@all",
    "message": "What is 2+2?",
    "aggregation_strategy": "first_success"
  }'
```

---

## 🔧 Phase 7 Features

### API Authentication

```bash
# Create API key
curl -X POST http://localhost:8765/api/admin/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "my-app", "rate_limit_rpm": 100}'

# Use API key
curl -X POST http://localhost:8765/api/ask \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"provider": "qwen", "message": "Hello"}'
```

### Rate Limiting

- Token bucket algorithm
- Default: 60 requests/minute
- Per-key rate limit override
- Burst support

### Response Caching

```bash
# Check cache stats
curl http://localhost:8765/api/cache/stats

# Response
{
  "hits": 15,
  "misses": 45,
  "hit_rate": 0.25,
  "total_entries": 30,
  "expired_entries": 5
}

# Clear cache
curl -X DELETE http://localhost:8765/api/cache
```

### Prometheus Metrics

```bash
curl http://localhost:8765/metrics

# Output
gateway_requests_total{provider="qwen",status="completed"} 150
gateway_request_latency_seconds_bucket{provider="qwen",le="5.0"} 120
gateway_cache_hits_total 15
gateway_cache_misses_total 45
```

---

## 📦 Providers

### Provider Matrix

| Provider | Command | Backend | Best For | Status |
|----------|---------|---------|----------|--------|
| **Gemini** | `gw-gemini` | WezTerm | Frontend, review | ✅ |
| **DeepSeek** | `gw-deepseek` | CLI Exec | Deep reasoning | ✅ |
| **Codex** | `gw-codex` | CLI Exec | Backend, API | ✅ |
| **OpenCode** | `gw-opencode` | CLI Exec | General coding | ✅ |
| **Kimi** | `gw-kimi` | CLI Exec | Chinese, long context | ✅ |
| **Qwen** | `gw-qwen` | CLI Exec | Multilingual | ✅ |
| **iFlow** | `gw-iflow` | CLI Exec | Workflow | ✅ |

> **Note**: Claude is the orchestrator (主脑) and does not participate in task dispatch.

---

## 🔧 Installation

### Prerequisites

- **Python 3.9+**
- **WezTerm** (recommended) or tmux
- Provider CLIs: `codex`, `gemini`, `opencode`, `deepseek`, `kimi`, `qwen`, `iflow`

### Install

```bash
# Clone repository
git clone https://github.com/LeoLin990405/ai-router-ccb.git ~/.local/share/codex-dual

# Install dependencies
pip install fastapi uvicorn pyyaml aiohttp prometheus-client

# Add to PATH
export PATH="$HOME/.local/share/codex-dual/bin:$PATH"

# Source shell functions
echo 'source ~/.ccb/gateway-functions.sh' >> ~/.zshrc
```

### Configuration

```yaml
# ~/.ccb/gateway.yaml
server:
  host: "127.0.0.1"
  port: 8765

default_provider: "qwen"

providers:
  gemini:
    enabled: true
    backend_type: "cli_exec"
    cli_command: "gemini"
    timeout_s: 300
  # ... other providers
```

---

## 📊 Performance

### Provider Latency (Typical)

| Provider | Avg Latency | Use Case |
|----------|-------------|----------|
| Kimi | ~9s | Chinese content |
| Qwen | ~14s | Multilingual |
| iFlow | ~17s | Workflow |
| Codex | ~19s | Code generation |
| OpenCode | ~27s | General coding |
| Gemini | ~31s | Frontend, review |
| DeepSeek | ~47s | Deep reasoning |

---

## 🙏 Acknowledgements

- **[bfly123/claude_code_bridge](https://github.com/bfly123/claude_code_bridge)** - Original multi-AI collaboration framework
- **[Grafbase/Nexus](https://github.com/grafbase/nexus)** - AI gateway architecture inspiration

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
