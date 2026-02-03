<p align="center">
  <img src="https://img.shields.io/github/stars/LeoLin990405/ai-router-ccb?style=social" alt="Stars">
  <img src="https://img.shields.io/github/license/LeoLin990405/ai-router-ccb?color=blue" alt="License">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
</p>

<h1 align="center">
  <br>
  🤖
  <br>
  CCB Gateway
  <br>
</h1>

<h4 align="center">Enterprise-Grade Multi-AI Orchestration Platform</h4>

<p align="center">
  <em>Claude as orchestrator, unified Gateway API managing 7 AI providers with real-time monitoring and model switching</em>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-ccb-cli">ccb-cli</a> •
  <a href="#-web-ui">Web UI</a> •
  <a href="#-api-reference">API</a> •
  <a href="#-model-switching">Model Switching</a>
</p>

<p align="center">
  <strong>English</strong> | <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img src="screenshots/webui-demo.gif" alt="CCB Gateway Web UI Demo" width="700">
</p>

---

## Overview

**CCB Gateway** is a production-ready multi-AI orchestration platform where **Claude serves as the orchestrator**, intelligently dispatching tasks to 7 AI providers through a unified Gateway API.

```
                    ┌─────────────────────────────┐
                    │   Claude (Orchestrator)     │
                    │      Claude Code CLI        │
                    └─────────────┬───────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
    ┌─────────▼─────────┐ ┌──────▼──────┐ ┌─────────▼─────────┐
    │   ccb-cli (NEW)   │ │ Gateway API │ │   ccb-submit      │
    │  Direct CLI call  │ │  REST/WS    │ │   Async Queue     │
    └─────────┬─────────┘ └──────┬──────┘ └─────────┬─────────┘
              │                  │                   │
              └──────────────────┼───────────────────┘
                                 │
          ┌───────────┬──────────┼──────────┬───────────┐
          ▼           ▼          ▼          ▼           ▼
     ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
     │  Kimi   │ │  Qwen   │ │DeepSeek │ │  Codex  │ │ Gemini  │
     │  🚀 7s  │ │  🚀 12s │ │  ⚡ 16s │ │ 🐢 48s  │ │ 🐢 71s  │
     └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
                      ┌─────────┐ ┌─────────┐
                      │  iFlow  │ │OpenCode │
                      │  ⚡ 25s │ │  ⚡ 42s │
                      └─────────┘ └─────────┘
```

### Why CCB Gateway?

| Challenge | Solution |
|-----------|----------|
| Multiple AI CLIs with different interfaces | **Unified Gateway API** + **ccb-cli** for all providers |
| Manual provider selection | **Intelligent routing** with speed-tiered fallback |
| No model switching within providers | **Dynamic model selection** (o3, gpt-4o, gemini-3-flash, etc.) |
| No visibility into AI operations | **Real-time monitoring** with WebSocket + Web UI |
| No caching or retry logic | **Built-in caching, retry, and fallback chains** |
| Can't see AI thinking process | **Thinking chain & raw output capture** |

---

## ✨ Features

### 🆕 ccb-cli (v0.11)

Direct CLI tool with model selection - no Gateway required:

```bash
ccb-cli <provider> [model] <prompt>
```

| Provider | Models | Example |
|----------|--------|---------|
| **Codex** | o3, o4-mini, o1-pro, gpt-4o, gpt-5.2-codex | `ccb-cli codex o3 "complex algorithm"` |
| **Gemini** | 3f, 3p, 2.5f, 2.5p | `ccb-cli gemini 3f "React component"` |
| **OpenCode** | mm, kimi, ds, glm | `ccb-cli opencode mm "general task"` |
| **DeepSeek** | reasoner, chat | `ccb-cli deepseek chat "quick question"` |
| **Kimi** | thinking, normal | `ccb-cli kimi thinking "detailed analysis"` |
| **iFlow** | thinking, normal | `ccb-cli iflow "workflow task"` |
| **Qwen** | - | `ccb-cli qwen "code generation"` |

### Core Gateway

- **REST API** - `POST /api/ask`, `GET /api/reply/{id}`, `GET /api/status`
- **WebSocket** - Real-time events at `/api/ws`
- **Priority Queue** - SQLite-backed request prioritization
- **Multi-Backend** - HTTP API, CLI Exec, WezTerm integration
- **Health Monitoring** - Automatic provider health checks

### Production Features

- **API Authentication** - API key-based auth with SHA-256 hashing
- **Rate Limiting** - Token bucket algorithm, per-key limits
- **Response Caching** - SQLite cache with TTL and pattern exclusion
- **Retry & Fallback** - Exponential backoff, automatic provider fallback
- **Parallel Queries** - Query multiple providers simultaneously
- **Prometheus Metrics** - `/metrics` endpoint for monitoring
- **Streaming** - Server-Sent Events for real-time responses

### Provider Speed Tiers

| Tier | Providers | Response Time | Best For |
|------|-----------|---------------|----------|
| 🚀 **Fast** | Kimi, Qwen | 5-15s | Quick tasks, simple questions |
| ⚡ **Medium** | DeepSeek, iFlow, OpenCode | 15-60s | Complex reasoning, coding |
| 🐢 **Slow** | Codex, Gemini | 60-120s | Deep analysis, reviews |

---

## 🚀 Quick Start

### Method 1: ccb-cli (Recommended)

No Gateway required - direct CLI access with model selection:

```bash
# Install (already included in ccb-dual)
# Scripts at ~/.ccb_config/scripts/ccb-cli

# Quick Chinese Q&A
ccb-cli kimi "什么是递归"

# Complex algorithm with o3
ccb-cli codex o3 "Design LRU cache algorithm"

# Frontend with Gemini 3 Flash
ccb-cli gemini 3f "React login component"

# Fast response
ccb-cli deepseek chat "HTTP status 200 means?"

# Detailed reasoning
ccb-cli kimi thinking "Analyze this problem step by step"
```

### Method 2: Gateway API

Full-featured async API with caching, retry, and monitoring:

```bash
# Start Gateway
cd ~/.local/share/codex-dual
python3 -m lib.gateway.gateway_server --port 8765

# Submit request
curl -X POST http://localhost:8765/api/ask \
  -H "Content-Type: application/json" \
  -d '{"provider": "kimi", "message": "Hello"}'

# Get response
curl "http://localhost:8765/api/reply/{request_id}"
```

### Method 3: ccb-submit (Async)

```bash
# Async submission with polling
REQUEST_ID=$(ccb-submit kimi "Hello")
ccb-query get $REQUEST_ID
```

---

## 🛠️ ccb-cli

### Installation

```bash
# Already installed at
~/.ccb_config/scripts/ccb-cli

# Add to PATH (if not already)
export PATH="$HOME/.ccb_config/scripts:$PATH"
```

### Model Quick Reference

```bash
# Codex models (OpenAI)
ccb-cli codex o3 "..."        # Best reasoning
ccb-cli codex o4-mini "..."   # Fast
ccb-cli codex gpt-4o "..."    # Multimodal
ccb-cli codex o1-pro "..."    # Pro reasoning

# Gemini models
ccb-cli gemini 3f "..."       # Gemini 3 Flash (fast)
ccb-cli gemini 3p "..."       # Gemini 3 Pro (powerful)
ccb-cli gemini 2.5f "..."     # Gemini 2.5 Flash
ccb-cli gemini 2.5p "..."     # Gemini 2.5 Pro

# OpenCode models
ccb-cli opencode mm "..."     # MiniMax M2.1
ccb-cli opencode kimi "..."   # Kimi via OpenCode
ccb-cli opencode ds "..."     # DeepSeek Reasoner

# DeepSeek modes
ccb-cli deepseek reasoner "..." # Deep reasoning
ccb-cli deepseek chat "..."     # Fast chat

# Thinking mode (Kimi/iFlow)
ccb-cli kimi thinking "..."     # Show reasoning chain
ccb-cli iflow thinking "..."    # GLM with thinking
```

### Task → Model Selection

| Task Type | Recommended Command |
|-----------|---------------------|
| Complex Algorithm | `ccb-cli codex o3 "..."` |
| Quick Code | `ccb-cli codex o4-mini "..."` |
| Frontend Dev | `ccb-cli gemini 3f "..."` |
| Deep Analysis | `ccb-cli gemini 3p "..."` |
| Chinese Q&A | `ccb-cli kimi "..."` |
| Detailed Reasoning | `ccb-cli kimi thinking "..."` |
| Fast Dialog | `ccb-cli deepseek chat "..."` |
| Image Analysis | `ccb-cli codex gpt-4o "..."` |

---

## 🖥️ Web UI

Access at `http://localhost:8765/` after starting Gateway.

<p align="center">
  <img src="screenshots/dashboard.png" alt="Dashboard" width="700">
  <br>
  <em>Dashboard - Real-time gateway stats and provider status</em>
</p>

### Tabs

| Tab | Shortcut | Description |
|-----|----------|-------------|
| **Dashboard** | `1` | Gateway stats, provider status, activity logs |
| **Monitor** | `2` | Real-time AI output streaming (Grid/Focus view) |
| **Requests** | `3` | Request history with search and filters |
| **Test** | `4` | Interactive API testing console |
| **Compare** | `5` | Side-by-side provider comparison |
| **API Keys** | `6` | API key management |
| **Config** | `7` | Gateway configuration viewer |

<p align="center">
  <img src="screenshots/monitor.png" alt="Live Monitor" width="700">
  <br>
  <em>Monitor - Watch AI responses stream in real-time</em>
</p>

### Features

- **Dark/Light Theme** - Toggle with `D` key
- **i18n Support** - English and Chinese
- **Keyboard Shortcuts** - `1-7` tabs, `R` refresh, `?` help
- **Real-time Updates** - WebSocket-powered live data

---

## 📡 API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ask` | Submit request |
| `GET` | `/api/reply/{id}` | Get response |
| `GET` | `/api/status` | Gateway status |
| `GET` | `/api/requests` | List requests |
| `GET` | `/metrics` | Prometheus metrics |

### Provider Groups

```bash
# All 7 providers
curl -d '{"provider": "@all", "message": "test"}' ...

# Fast providers only
curl -d '{"provider": "@fast", "message": "test"}' ...

# Chinese-optimized
curl -d '{"provider": "@chinese", "message": "test"}' ...

# Coding tasks
curl -d '{"provider": "@coding", "message": "test"}' ...
```

---

## 🔄 Model Switching

### Available Models by Provider

| Provider | Available Models |
|----------|------------------|
| **Codex** | `o3`, `o4-mini`, `o3-mini`, `o1`, `o1-pro`, `gpt-5.2-codex`, `gpt-4.5`, `gpt-4.1`, `gpt-4o` |
| **Gemini** | `gemini-3-flash-preview`, `gemini-3-pro-preview`, `gemini-2.5-flash`, `gemini-2.5-pro` |
| **OpenCode** | `opencode/minimax-m2.1-free`, `opencode/kimi-k2.5-free`, `deepseek/deepseek-reasoner` |
| **DeepSeek** | `deepseek-reasoner`, `deepseek-chat` |
| **Kimi** | `kimi-for-coding` + `--thinking` option |
| **iFlow** | `GLM-4.7` + `--thinking` option |
| **Qwen** | `coder-model` (OAuth, single model) |

### Gateway Configuration

Edit `~/.ccb_config/gateway.yaml`:

```yaml
providers:
  codex:
    cli_args: ["exec", "--json", "-m", "o3"]  # Switch model here

  gemini:
    cli_args: ["-m", "gemini-3-flash-preview", "-p"]

  opencode:
    cli_args: ["run", "--format", "json", "-m", "opencode/minimax-m2.1-free"]
```

Restart Gateway after config changes.

---

## 📦 Installation

### Prerequisites

- Python 3.9+
- Provider CLIs: `codex`, `gemini`, `opencode`, `deepseek`, `kimi`, `qwen`, `iflow`

### Install

```bash
# Clone
git clone https://github.com/LeoLin990405/ai-router-ccb.git ~/.local/share/codex-dual

# Dependencies
pip install fastapi uvicorn pyyaml aiohttp prometheus-client

# Start Gateway
python3 -m lib.gateway.gateway_server --port 8765

# Or use ccb-cli directly (no Gateway needed)
ccb-cli kimi "Hello"
```

---

## 🔄 Recent Updates

### v0.11.x - ccb-cli & Model Switching (Latest)
- **ccb-cli** - Direct CLI tool with model selection
- **Model shortcuts** - `o3`, `3f`, `mm`, `reasoner`, `thinking`
- **expect scripts** - Automated CLI interaction
- **Updated documentation** - Comprehensive model guide

### v0.10.x - Live Monitor
- **Real-time AI Monitor** - Watch AI output as it streams
- **Grid/Focus Views** - Multi-provider or single-provider monitoring
- **WebSocket Integration** - Real-time stream_chunk events

### v0.9.x - Provider Optimization
- **Provider Speed Tiers** - Fast/Medium/Slow classification
- **Gemini OAuth Auto-Refresh** - Seamless token management
- **Provider Groups** - `@fast`, `@chinese`, `@coding`

---

## 🙏 Acknowledgements

- **[bfly123/claude_code_bridge](https://github.com/bfly123/claude_code_bridge)** - Original multi-AI collaboration framework

---

## 📄 License

MIT License - See [LICENSE](LICENSE)

---

<p align="center">
  <sub>Built with collaboration between human and AI</sub>
  <br>
  <sub>⭐ Star this repo if you find it useful!</sub>
</p>
