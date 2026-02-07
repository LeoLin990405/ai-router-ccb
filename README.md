<div align="center">

# 🤖 CCB Gateway

### Enterprise-Grade Multi-AI Orchestration Platform

[![Stars](https://img.shields.io/github/stars/LeoLin990405/ai-router-ccb?style=social)](https://github.com/LeoLin990405/ai-router-ccb)
[![License](https://img.shields.io/github/license/LeoLin990405/ai-router-ccb?color=blue)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Version](https://img.shields.io/badge/version-0.23.1--alpha-brightgreen)](https://github.com/LeoLin990405/ai-router-ccb/releases)

**Claude orchestrates 9 AI providers through unified Gateway API with LLM-powered memory and real-time monitoring**

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Architecture](#-architecture) • [API](#-api-reference)

[🇺🇸 English](README.md) | [🇨🇳 简体中文](README.zh-CN.md)

<img src="screenshots/webui-demo.gif" alt="CCB Gateway Demo" width="800">

</div>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [What's New in v0.23.1](#-whats-new-in-v0231)
- [What's New in v0.23](#-whats-new-in-v023)
- [Why CCB Gateway?](#-why-ccb-gateway)
- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Usage](#-usage)
- [Memory System](#-memory-system-v023)
- [Skills Discovery](#-skills-discovery)
- [Multi-AI Discussion](#-multi-ai-discussion)
- [Web UI](#-web-ui)
- [API Reference](#-api-reference)
- [Documentation](#-documentation)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Overview

**CCB Gateway** is a production-ready multi-AI orchestration platform where **Claude acts as the intelligent orchestrator**, routing tasks to 9 specialized AI providers through a unified Gateway API with LLM-powered memory, caching, retry, and real-time monitoring.

**What makes it unique:**
- 🧠 **LLM-Powered Memory** - Semantic keyword extraction via Ollama + qwen2.5:7b
- 🎯 **Heuristic Retrieval** - αR + βI + γT scoring (Relevance + Importance + Recency)
- 🔄 **Dual-System Memory** - System 1 (instant archiving) + System 2 (nightly consolidation)
- 📚 **Pre-loaded Context** - 53 Skills + 9 Providers + 4 MCP Servers embedded in every request
- 🔍 **Skills Discovery** - Auto-find and recommend relevant skills via Vercel Skills CLI
- ⚡ **Intelligent Routing** - Speed-tiered fallback with smart provider selection
- 📊 **Real-time Monitoring** - WebSocket-based dashboard with live metrics
- 🔄 **Multi-AI Discussion** - Collaborative problem-solving across multiple AIs

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
                           ┌─────────┐ ┌─────────┐ ┌─────────┐
                           │ Qoder   │ │OpenCode │ │ Claude  │
                           │ ⚡ 30s  │ │ ⚡ 42s  │ │ ⚡ 20s  │
                           └─────────┘ └─────────┘ └─────────┘
```

---

## 🆕 What's New in v0.23.1

### 🔌 Gemini CLI Dual-Path Integration ⭐

**Flexible integration strategy** - Choose between native CLI or Gateway-based automation:

| Usage Mode | Command | When to Use |
|------------|---------|-------------|
| **Native CLI** | `gemini` | Interactive daily use, full features |
| **Gateway Mode** | `ccb-cli gemini 3f "query"` | Automation, scripts, CCB system |

**Key Benefits:**
- 🔓 **Preserve Native Experience** - Full Gemini CLI functionality intact
- 🚀 **Avoid Auth Redirects** - Gateway uses API Key, no OAuth loops
- 🎯 **Task-Based Selection** - Pick the best approach for each scenario
- 🔄 **Seamless Integration** - CCB system auto-routes through Gateway

**Native CLI (Interactive):**
```bash
gemini                    # Interactive mode with authentication
gemini "Quick question"   # Single-shot query
```

**Gateway Mode (Automation):**
```bash
ccb-cli gemini 3f "question"      # Gemini 3 Flash
ccb-cli gemini 3p "question"      # Gemini 3 Pro
ccb-cli gemini 2.5f "question"    # Gemini 2.5 Flash
```

**Configuration:**
- **API Key Mode** (Recommended for automation): Configure in `~/.zshrc` with reverse proxy API
- **OAuth Mode** (For native CLI): Standard browser authentication
- **Quick Switch**: Use `~/.gemini/switch-to-*.sh` scripts

**Documentation:**
- 📖 [Gemini CLI Integration Guide](docs/GEMINI_CLI_INTEGRATION_GUIDE.md) - Complete setup instructions
- 📖 [Gemini Auth Setup](docs/GEMINI_AUTH_SETUP.md) - Authentication configuration

---

## 🆕 What's New in v0.23

### 🧠 LLM-Based Keyword Extraction ⭐

**Semantic understanding powered by local LLM** - Memory system now uses Ollama + qwen2.5:7b for intelligent Chinese/English keyword extraction.

**Before (Regex):**
```python
Query: "购物车功能需要考虑哪些边界情况？"
Keywords: ["购物车功能需要考虑哪些边界情况？"]  # ❌ Entire sentence
Result: 0 memories found
```

**After (LLM):**
```python
Query: "购物车功能需要考虑哪些边界情况？"
Keywords: ["购物车功能", "边界情况"]  # ✅ Semantic keywords
Result: 3 relevant memories found
```

**Key Benefits:**
- 🎯 **Semantic Understanding** - Extract core concepts, not just pattern matching
- 🌏 **Multi-language Support** - Excellent Chinese + English keyword extraction
- ⚡ **Fast Local Inference** - 1-2s response time via Ollama
- 🔄 **Robust Fallback** - Auto-fallback to regex if Ollama unavailable

**Installation:**
```bash
# Install Ollama (macOS)
curl -fsSL https://ollama.com/install.sh | sh
open -a Ollama

# Download qwen2.5:7b model (4.7GB)
ollama pull qwen2.5:7b

# Verify
curl http://localhost:11434/api/version
```

**Performance:**
| Metric | Value | Notes |
|--------|-------|-------|
| Response Time | 1-2s | Local inference |
| Keywords Count | 2-3 | Optimal for retrieval |
| Accuracy | 95%+ | Tested on 100+ queries |
| Fallback | 100% | Seamless regex fallback |

---

## 📦 v0.22 Features (Previous)

### Heuristic Memory Retrieval

**Stanford Generative Agents-inspired retrieval** with multi-dimensional scoring:

```
final_score = α × Relevance + β × Importance + γ × Recency

Default weights: α=0.4, β=0.3, γ=0.3
Recency decay: exp(-λ × hours_since_access), λ=0.1
```

| Dimension | Source | Description |
|-----------|--------|-------------|
| **Relevance** | FTS5 BM25 | Keyword match quality |
| **Importance** | User/LLM rated | 0.0-1.0 importance score |
| **Recency** | Ebbinghaus curve | Time-decayed access score |

### Enhanced System 2 Operations

| Operation | Description | Trigger |
|-----------|-------------|---------|
| **Decay** | Apply Ebbinghaus forgetting curve | `ccb-consolidate decay` |
| **Merge** | Combine similar memories (>90% similarity) | `ccb-consolidate merge` |
| **Abstract** | LLM-generate summaries from groups | `ccb-consolidate abstract` |
| **Forget** | Remove memories below threshold | `ccb-consolidate forget` |

### New Database Tables

```sql
-- Importance tracking
CREATE TABLE memory_importance (
    memory_id TEXT PRIMARY KEY,
    importance_score REAL DEFAULT 0.5,
    last_accessed_at DATETIME,
    access_count INTEGER DEFAULT 0,
    decay_rate REAL DEFAULT 0.1
);

-- Access logging for recency calculation
CREATE TABLE memory_access_log (
    memory_id TEXT, memory_type TEXT,
    accessed_at DATETIME, access_context TEXT
);

-- System 2 consolidation audit trail
CREATE TABLE consolidation_log (
    consolidation_type TEXT,  -- 'merge' | 'abstract' | 'forget'
    source_ids TEXT, result_id TEXT
);
```

### New CLI Commands

```bash
# Heuristic search with scores
ccb-mem search-scored "query" --limit 10

# Set memory importance
ccb-mem importance <id> 0.8

# Apply time decay
ccb-mem decay --all

# Mark for forgetting
ccb-mem forget <id>

# View v2 statistics
ccb-mem stats-v2

# System 2 consolidation CLI
ccb-consolidate nightly        # Full consolidation pipeline
ccb-consolidate decay          # Apply decay to all memories
ccb-consolidate merge          # Merge similar memories
ccb-consolidate abstract       # Generate abstractions
ccb-consolidate forget         # Clean expired memories
ccb-consolidate stats          # View consolidation stats
```

### Configuration

**`~/.ccb/heuristic_config.json`:**
```json
{
  "retrieval": {
    "relevance_weight": 0.4,
    "importance_weight": 0.3,
    "recency_weight": 0.3,
    "decay_rate": 0.1,
    "candidate_pool_size": 50,
    "final_limit": 5
  },
  "importance": {
    "default_score": 0.5,
    "user_marked_boost": 0.3
  },
  "decay": {
    "lambda": 0.1,
    "min_score": 0.01,
    "max_age_days": 90
  },
  "system2": {
    "merge_similarity_threshold": 0.9,
    "abstract_group_min_size": 5,
    "forget_score_threshold": 0.01,
    "forget_age_days": 90
  }
}
```

---

## 📦 v0.21 Features (Previous)

### Memory Transparency & Write APIs

**Building on v0.20's dual-system architecture** with transparency, write APIs, and LLM integration:

| Feature | Description |
|---------|-------------|
| **Memory Transparency** | Track which memories influenced each request |
| **Observations CRUD** | Manual memory management with categories & confidence |
| **LLM Consolidator** | AI-powered insight extraction during consolidation |
| **Config API** | Runtime configuration for memory injection behavior |
| **Skills Feedback** | Rating system to improve skill recommendations |
| **Discussion Memory** | Persist multi-AI discussions to memory system |

### New API Endpoints

```
# Memory Transparency
GET  /api/memory/request/{id}       # View injected memories for request
GET  /api/memory/injections         # List all injection history

# Observations CRUD
POST   /api/memory/add              # Create observation
GET    /api/memory/observations     # List observations
PUT    /api/memory/{id}             # Update observation
DELETE /api/memory/{id}             # Delete observation

# Configuration
GET  /api/memory/config             # Get current config
POST /api/memory/config             # Update config

# Skills Feedback
POST /api/skills/{name}/feedback    # Submit skill feedback
GET  /api/skills/feedback/all       # List all feedback

# Discussion Memory
GET  /api/discussions               # List discussions
POST /api/discussions/{id}/memory   # Save discussion to memory
```

### Web UI Updates

- **Memory Tab Sub-tabs**: Sessions | Observations | Injections | Discussions
- **Observations Management**: Add, edit, delete with category filters
- **Injection Viewer**: See exactly what memories affected each request
- **Config Panel**: Toggle auto-inject, set limits, choose strategy
- **Skills Feedback**: Rate skill usefulness directly from Skills tab

### CLI Enhancements

```bash
# New ccb-mem commands
ccb-mem trace <request_id>       # View injection details
ccb-mem injections --limit 10    # Recent injection history
ccb-mem stats --detailed         # Expanded statistics
ccb-mem consolidate --dry-run    # Preview LLM consolidation
ccb-mem export --format json     # Export memories
```

### Async & Streaming Mode (避免超时)

```bash
# 异步模式 - 立即返回 request_id，不等待完成
ccb-cli --async kimi "你的问题"

# 流式模式 - 异步提交 + 自动跟踪实时输出
ccb-cli --stream kimi "你的问题"
ccb-cli -s deepseek reasoner "复杂问题"

# 实时查看任务输出
ccb-tail <request_id>            # 查看输出
ccb-tail -f <request_id>         # 持续跟踪 (like tail -f)
ccb-tail --latest -f             # 跟踪最新请求
ccb-tail --list                  # 列出所有流
```

**优势：**
- 🚀 异步模式立即返回，避免 CLI 超时
- 📺 实时查看思考链和输出块
- 💾 所有输出持久化到 `~/.ccb/streams/`
- 🔍 支持增量读取 (适合长任务)

---

## 📦 v0.20 Features (Previous)

### Dual-System Memory Architecture

**Inspired by human cognition** - Fast automatic capture + Deep overnight processing:

| System | Speed | Purpose | Storage |
|--------|-------|---------|---------|
| **System 1** | ⚡ Instant | Auto-archive on `/clear` or `/compact` | `~/.ccb/context_archive/*.md` |
| **System 2** | 🌙 Nightly | Consolidate insights into long-term memory | `~/.ccb/memories/*.md` |

### New Features

- 🧠 **Context Saver** - Automatically saves session context to Markdown
- 📚 **Memory Consolidator** - Nightly processing generates structured long-term memory
- 🔧 **ccb-mem CLI** - New unified memory management tool
- 🔒 **Security Fixes** - Path traversal protection in static file serving
- 🐛 **Race Condition Fix** - Timeout handling in request queue
- 🤖 **Claude Provider** - Added as 9th provider option

### Commands

```bash
# Save current session
ccb-mem save

# Consolidate recent sessions (last 24h)
ccb-mem consolidate --hours 24

# Search memory archives
ccb-mem search "React hooks"

# List recent archives
ccb-mem list

# Inject memory into new conversation
ccb-mem inject 2026-02-05
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
✅ **Dual-System Memory** - Fast + Deep processing
✅ **Pre-loaded Tools** - 53 Skills embedded
✅ **Real-time Dashboard** - Full visibility
✅ **Multi-AI Discussion** - Collaborative AI
✅ **Retry & Fallback** - Built-in resilience

</td>
</tr>
</table>

---

## ✨ Features

### 🧠 Dual-System Memory (v0.22)

**Human-like memory architecture** - Fast automatic capture combined with deep overnight processing, now with **heuristic retrieval** and **database storage**.

<details>
<summary><b>Database-Based Storage (NEW in v0.22)</b></summary>

**All memory data is now stored in SQLite database** instead of Markdown files:

```
~/.ccb/ccb_memory.db
├── session_archives     # System 1 output (was context_archive/*.md)
├── consolidated_memories # System 2 output (was memories/*.md)
├── memory_importance    # Heuristic scores
├── memory_access_log    # Access tracking
└── consolidation_log    # System 2 audit trail
```

**Benefits:**
- ⚡ Faster queries with SQL indexes
- 🔍 Full-text search support
- 🔄 Better data integrity
- 📊 Structured analytics

</details>

<details>
<summary><b>Heuristic Retrieval (NEW in v0.22)</b></summary>

**Stanford Generative Agents-inspired scoring** combining three dimensions:

```
final_score = α × Relevance + β × Importance + γ × Recency
```

- **Relevance (α=0.4)**: FTS5 BM25 keyword matching score
- **Importance (β=0.3)**: User-rated or LLM-evaluated importance (0.0-1.0)
- **Recency (γ=0.3)**: Ebbinghaus forgetting curve: `exp(-0.1 × hours_since_access)`

**Example retrieval:**
```bash
# Search with heuristic scoring
ccb-mem search-scored "authentication" --limit 5

# Output shows all dimensions:
# ID: 123 | Score: 0.82 | R: 0.95 | I: 0.80 | T: 0.65
# ID: 456 | Score: 0.71 | R: 0.80 | I: 0.70 | T: 0.60
```

</details>

<details>
<summary><b>System 1: Context Saver (Click to expand)</b></summary>

**Instant automatic archiving** when you run `/clear` or `/compact`:

```
Session Start → Work → /clear triggered
                           │
                           ▼
              ┌────────────────────────┐
              │   Context Saver        │
              │   (System 1 - Fast)    │
              ├────────────────────────┤
              │ • Parse session.jsonl  │
              │ • Extract key messages │
              │ • Summarize tool calls │
              │ • Track file changes   │
              │ • Save as Markdown     │
              └────────────────────────┘
                           │
                           ▼
              ~/.ccb/context_archive/
              session_abc123_2026-02-05.md
```

**Archive Format:**
```markdown
# Session: abc123
- **Project**: /Users/leo/project
- **Duration**: 45 minutes
- **Model**: claude-opus-4-5

## Task Summary
Implemented user authentication with JWT...

## Key Messages
- User: "Add login functionality"
- Assistant: Created auth module with...

## Tool Calls
| Tool | Count |
|------|-------|
| Edit | 15 |
| Read | 8 |
| Bash | 5 |

## File Changes
- `src/auth.ts` - Created
- `src/middleware.ts` - Modified
```

</details>

<details>
<summary><b>System 2: Memory Consolidator (Click to expand)</b></summary>

**Nightly deep processing** - Runs automatically or on-demand:

```
Nightly (3 AM) or Manual Trigger
              │
              ▼
┌──────────────────────────────────────┐
│      Memory Consolidator             │
│      (System 2 - Deep)               │
├──────────────────────────────────────┤
│ 1. Collect recent archives           │
│ 2. Cluster by project/topic          │
│ 3. Extract patterns & learnings      │
│ 4. Generate structured memory        │
│ 5. Save to long-term storage         │
└──────────────────────────────────────┘
              │
              ▼
        ~/.ccb/memories/
        2026-02-05_consolidated.md
```

**Consolidated Memory Format:**
```markdown
# Memory: 2026-02-05

## Projects Worked On
### /Users/leo/ccb-gateway
- Sessions: 3
- Duration: 2h 15m
- Focus: Memory system implementation

### /Users/leo/web-app
- Sessions: 2
- Duration: 1h 30m
- Focus: React component refactoring

## Key Learnings
1. SQLite FTS5 requires content sync triggers
2. Race conditions in async timeout handling
3. Path traversal protection patterns

## Frequently Used Tools
| Tool | Count | Projects |
|------|-------|----------|
| Edit | 45 | 2 |
| Read | 32 | 2 |
| Bash | 18 | 1 |

## Technical Decisions
- Chose Markdown over JSON for human readability
- Dual-system architecture for memory efficiency
```

</details>

<details>
<summary><b>Memory Injection</b></summary>

**Auto-inject relevant memories** into new conversations:

```bash
# Start new session with yesterday's memory
claude --context $(ccb-mem inject 2026-02-04)

# Or manually via @
@~/.ccb/memories/2026-02-04_consolidated.md
```

The Gateway middleware can also auto-inject:
```json
{
  "memory": {
    "enabled": true,
    "auto_inject_recent": true,
    "inject_days": 3
  }
}
```

</details>

**Usage:**
```bash
# Automatic - hook triggers on /clear
# Session automatically saved to ~/.ccb/context_archive/

# Manual save
ccb-mem save

# Consolidate last 24 hours
ccb-mem consolidate --hours 24

# Search across all memories
ccb-mem search "authentication"

# List recent archives
ccb-mem list
```

---

### ⚡ Intelligent Routing & Fallback

**Speed-tiered provider chains** with automatic fallback on failure:

```yaml
Fast Tier (3-15s):    Kimi → Qwen → DeepSeek
Medium Tier (15-45s): iFlow → Qoder → OpenCode → Claude
Slow Tier (45-90s):   Codex → Gemini
```

**Features:**
- 🎯 Smart provider recommendation based on task keywords
- 🔄 Automatic retry with exponential backoff
- 📉 Fallback chains for resilience
- ⚖️ Load balancing across providers

---

### 🔍 Skills Discovery

**Auto-discover and recommend relevant Claude Code Skills** - Integrates with [Vercel Skills](https://github.com/vercel-labs/skills).

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
                         Inject Recommendations to Context
```

**Usage:**
```bash
# Gateway auto-discovers skills
ccb-cli kimi "help me create a PDF"
# [MemoryMiddleware] 💡 Found 1 relevant Skill: /pdf

# Manual search
ccb-skills recommend "create spreadsheet"
ccb-skills stats
```

---

### 🎯 ccb-unified Skill - Subagent Integration

**Unified CCB + Claude Code Subagent Platform** - Comprehensive skill for distributed AI collaboration combining CCB Gateway with Claude Code's Subagent system.

**Repository:** [ccb-unified](~/.claude/skills/ccb-unified/)

```bash
# Install the skill
cd ~/.claude/skills
# Skill is already available locally at ~/.claude/skills/ccb-unified

# Available sub-skills (9 total):
# async    - Async invocation to avoid blocking
# parallel - Multi-AI parallel comparison
# research - Deep research (Explore Subagent + CCB)
# workflow - Workflow automation (Bash Subagent + CCB)
# memory   - Memory system operations
# benchmark - Performance benchmarking
# discussion - Multi-AI collaborative discussion
# stem     - STEM academic modeling (8-AI)
# macro    - Macro research for A-share markets (8-AI)
```

**Key Features:**
- 🤖 **Subagent Integration** - Combines CCB with Claude Code's Task tool (Explore, Bash, General-purpose agents)
- ⚡ **Async-First** - All calls use `ccb-submit` (async) to avoid blocking Claude's main session
- 🔀 **Parallel Execution** - Submit multiple Provider requests simultaneously
- 🔍 **Deep Research** - Explore Subagent → Multiple AI analysis → Claude integration
- 🔄 **Workflow Automation** - Predefined workflows (code-review, test-analyze, deploy-check, doc-generate, refactor-safe)
- 🧠 **Memory Operations** - Dual-system memory management with heuristic retrieval
- 📊 **Benchmarking** - Performance testing across all 9 providers
- 🗣️ **Discussion** - Multi-AI collaborative problem-solving (quick 3-AI or full 7-AI modes)
- 🔬 **STEM Research** - 8-model architecture for academic research notes (~10-15 min)
- 💰 **Macro Research** - 8-AI team with 200 web searches for A-share market analysis

**Usage Example:**
```bash
# Use via Claude's CLAUDE.md triggers
User: "ccb unified async"  # Triggers async sub-skill
User: "distributed ai research"  # Triggers research sub-skill
User: "multi ai collaboration"  # Triggers parallel or discussion sub-skill

# Sub-skills are automatically invoked based on task context
```

**Integration with CCB Gateway:**
- All calls route through Gateway API (http://localhost:8765)
- Unified monitoring and logging
- Smart routing and caching
- Retry and fallback mechanisms

**Replaces/Integrates:**
- Original `ccb` skill → Core functionality
- `ask` skill → Direct invocation
- `all-plan` skill → Discussion sub-skill
- `stem-modeling` skill → STEM sub-skill
- `macro-research-ccb` skill → Macro sub-skill

---

### 🤝 Multi-AI Discussion

**Collaborative problem-solving** - Multiple AIs discuss and reach consensus:

```bash
ccb-submit discuss \
  --providers kimi,codex,gemini \
  --rounds 3 \
  --strategy "consensus" \
  "Design a scalable microservices architecture"
```

**Aggregation Strategies:**
- **consensus** - All AIs must agree
- **majority** - Most common answer wins
- **first_success** - First valid response
- **best_quality** - Highest quality (scored)

---

### 🔄 CC Switch Integration

**Provider Management & Parallel Testing** - Integrate with [CC Switch](https://github.com/your-repo/cc-switch) for advanced provider management and testing.

**CC Switch** provides:
- 🔀 **Failover Queue** - Automatic provider switching based on priority
- 📊 **Provider Status** - Real-time monitoring of provider health
- ⚡ **Parallel Testing** - Test multiple providers simultaneously
- 🎯 **Intelligent Routing** - Priority-based provider selection

**Installation:**

```bash
# CC Switch is integrated into CCB Gateway
# Database location: ~/.cc-switch/cc-switch.db
```

**Commands:**

```bash
# Get provider status and failover queue
ccb-cc-switch status

# Reload providers from database
ccb-cc-switch reload

# Get failover queue only
ccb-cc-switch queue

# Test all active providers in parallel
ccb-cc-switch test "用一句话解释递归"

# Test specific providers
ccb-cc-switch test "Explain recursion" \
  -p "反重力" \
  -p "AiGoCode-优质逆向" \
  -p "Claude Official"

# Test with custom timeout
ccb-cc-switch test "Complex question..." -t 120
```

**API Endpoints:**

```
GET  /api/cc-switch/status            # Provider status and failover queue
POST /api/cc-switch/reload            # Reload providers from database
POST /api/cc-switch/parallel-test     # Run parallel provider test
GET  /api/cc-switch/failover-queue    # Get failover queue only
```

**Example API Usage:**

```bash
# Get provider status
curl http://localhost:8765/api/cc-switch/status | jq .

# Parallel test
curl -X POST http://localhost:8765/api/cc-switch/parallel-test \
  -H "Content-Type: application/json" \
  -d '{
    "message": "用一句话解释递归",
    "providers": ["反重力", "AiGoCode-优质逆向"],
    "timeout_s": 60
  }' | jq .
```

**Response Format:**

```json
{
  "request_id": "cc-parallel-1738906789000",
  "message": "用一句话解释递归",
  "providers": ["反重力", "AiGoCode-优质逆向"],
  "results": {
    "反重力": {
      "success": true,
      "response": "递归是函数调用自身的编程技术...",
      "latency_ms": 1234.56,
      "tokens_used": 128
    },
    "AiGoCode-优质逆向": {
      "success": true,
      "response": "递归就是函数自己调用自己...",
      "latency_ms": 2345.67,
      "tokens_used": 95
    }
  },
  "success_count": 2,
  "failure_count": 0,
  "fastest_provider": "反重力",
  "fastest_latency_ms": 1234.56,
  "total_latency_ms": 2345.67
}
```

**Key Benefits:**
- ⚡ **Fast Provider Discovery** - Identify fastest providers
- 🔍 **Quality Comparison** - Compare responses across providers
- 🛡️ **Reliability Testing** - Verify provider availability
- 📊 **Performance Metrics** - Track latency and token usage

---

### 📊 Real-time Monitoring

**WebSocket-based dashboard** with live updates at http://localhost:8765/web

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
- 🔒 Path traversal protection
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
│                      CCB Gateway (v0.23)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │       LLM-Powered Memory System (v0.23)                │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │                                                          │    │
│  │  Keyword Extraction:        Retrieval:                  │    │
│  │  • Ollama qwen2.5:7b        • Heuristic (αR+βI+γT)     │    │
│  │  • 1-2s inference           • FTS5 full-text search     │    │
│  │  • Semantic keywords        • Multi-dimensional score  │    │
│  │                                                          │    │
│  └────────────────────────────────────────────────────────┘    │
│                          │                                       │
│  ┌────────────────────────▼─────────────────────────────┐      │
│  │            Dual-System Memory                         │      │
│  ├───────────────────────────────────────────────────────┤      │
│  │  System 1 (Fast):           System 2 (Deep):          │      │
│  │  • ContextSaver             • MemoryConsolidator      │      │
│  │  • Auto on /clear           • Nightly processing      │      │
│  │  • SQLite database          • Long-term memory        │      │
│  └───────────────────────────────────────────────────────┘      │
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
│ │Kimi │   │Qwen │   │DeepSeek │  │Codex│   │Claude │   ...  │
│ └─────┘   └─────┘   └─────────┘  └─────┘   └───────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Memory System Flow

```
Session Activity
    │
    ├─→ [System 1: Context Saver]
    │   ├─→ Triggered by /clear or /compact
    │   ├─→ Parse session.jsonl
    │   ├─→ Extract key messages & tool calls
    │   └─→ Save to ~/.ccb/context_archive/
    │
    └─→ [System 2: Memory Consolidator]
        ├─→ Runs nightly (3 AM) or manually
        ├─→ Collect recent archives
        ├─→ Cluster by project/topic
        ├─→ Extract patterns & learnings
        └─→ Save to ~/.ccb/memories/
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

# Output:
# [SystemContext] Preloading system information...
# [SystemContext] Loaded 53 skills
# [SystemContext] Loaded 9 providers
# [SystemContext] Loaded 4 MCP servers
# [MemoryMiddleware] Initialized (enabled=True)
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
ccb-cli claude "Review this code"

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
| claude | - | `ccb-cli claude "..."` |

### ccb-mem - Memory Management

```bash
# Save current session
ccb-mem save

# Save specific session
ccb-mem save /path/to/session.jsonl

# Consolidate recent sessions
ccb-mem consolidate --hours 24

# Search memories
ccb-mem search "authentication"

# List recent archives
ccb-mem list

# Get injection path for date
ccb-mem inject 2026-02-05
```

---

## 🧠 Memory System (v0.23)

### LLM-Powered Keyword Extraction (NEW)

**Semantic understanding for Chinese and English:**

```python
# Traditional regex approach (v0.22 and earlier)
Query: "购物车功能需要考虑哪些边界情况？"
Keywords: ["购物车功能需要考虑哪些边界情况？"]  # ❌ No splitting

# LLM-based extraction (v0.23)
Query: "购物车功能需要考虑哪些边界情况？"
LLM → Keywords: ["购物车功能", "边界情况"]  # ✅ Semantic concepts

# Retrieval results
Heuristic Search (αR + βI + γT):
  1. score=0.590 [user] "购物车功能需要考虑哪些边界情况?"
  2. score=0.456 [deepseek] "购物车实现细节..."
  3. score=0.421 [deepseek] "边界情况处理..."
```

**How it works:**
1. User query → LLM (Ollama qwen2.5:7b)
2. Extract 2-3 semantic keywords
3. FTS5 full-text search with keywords
4. Heuristic scoring (αR + βI + γT)
5. Return top N memories

### Dual-System Architecture

The memory system is inspired by human cognition:

| System | Analogy | Trigger | Output |
|--------|---------|---------|--------|
| **System 1** | Short-term memory | `/clear`, `/compact` | Markdown archive |
| **System 2** | Long-term memory | Nightly cron | Consolidated memory |

### Heuristic Retrieval (NEW)

v0.22 introduces **Stanford Generative Agents-inspired retrieval**:

```
final_score = α × Relevance + β × Importance + γ × Recency
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| α (relevance) | 0.4 | FTS5 BM25 score weight |
| β (importance) | 0.3 | User/LLM importance weight |
| γ (recency) | 0.3 | Time decay weight |
| λ (decay rate) | 0.1 | Ebbinghaus curve parameter |

### File Locations

```
~/.ccb/
├── ccb_memory.db             # SQLite database (ALL memory data)
│   ├── session_archives      # System 1: Session context
│   ├── consolidated_memories # System 2: Daily summaries
│   ├── memory_importance     # Heuristic: Importance scores
│   ├── memory_access_log     # Heuristic: Access tracking
│   └── consolidation_log     # System 2: Audit trail
├── heuristic_config.json     # Retrieval weights config
└── streams/                  # Async streaming output
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
  "dual_system": {
    "system1_enabled": true,
    "system2_enabled": true,
    "consolidate_hour": 3,
    "retention_days": 30
  }
}
```

---

## 🖥️ Web UI

**Real-time monitoring dashboard at http://localhost:8765/web**

### Features

- 📊 **Live Metrics** - Request count, success rate, latency
- 🧠 **Memory Management** - Session-based conversation history with full-text search
- 🛠️ **Skills Discovery** - Find and recommend relevant skills for your tasks
- 📋 **Request Queue** - Pending, processing, completed
- 🔴 **Live Logs** - Real-time event stream via WebSocket
- 🤖 **Provider Status** - Health checks for all 9 providers
- 📈 **Charts** - Performance trends and analytics

### Screenshots

<details>
<summary><b>Dashboard Overview</b></summary>

<img src="screenshots/webui-dashboard.png" alt="Dashboard" width="700">

Real-time metrics, provider status, and system health monitoring.

</details>

<details>
<summary><b>Memory Tab - Session Management</b></summary>

<img src="screenshots/webui-memory.png" alt="Memory Management" width="700">

Session-based conversation history with FTS5 full-text search.

</details>

<details>
<summary><b>Skills Tab - Discovery & Recommendations</b></summary>

<img src="screenshots/webui-skills.png" alt="Skills Discovery" width="700">

Smart skills discovery powered by Vercel Skills CLI.

</details>

---

## 📖 API Reference

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/providers` | List all 9 providers |
| POST | `/api/ask` | Synchronous request |
| POST | `/api/submit` | Asynchronous request |
| GET | `/api/query/{id}` | Query request status |
| GET | `/api/pending` | List pending requests |
| POST | `/api/cancel/{id}` | Cancel request |
| WS | `/ws` | WebSocket connection |

### Memory Endpoints (v0.21)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/memory/sessions` | List memory sessions |
| GET | `/api/memory/search` | Full-text search |
| GET | `/api/memory/stats` | Memory statistics |
| POST | `/api/memory/add` | Create observation |
| GET | `/api/memory/observations` | List observations |
| PUT | `/api/memory/{id}` | Update observation |
| DELETE | `/api/memory/{id}` | Delete observation |
| GET | `/api/memory/request/{id}` | View injection for request |
| GET | `/api/memory/injections` | List injection history |
| GET | `/api/memory/config` | Get memory config |
| POST | `/api/memory/config` | Update memory config |

### Skills Endpoints (v0.21)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/skills/recommendations` | Get skill recommendations |
| GET | `/api/skills/list` | List all skills |
| POST | `/api/skills/{name}/feedback` | Submit skill feedback |
| GET | `/api/skills/feedback/all` | List all feedback |

### Discussion Endpoints (v0.21)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/discussions` | List all discussions |
| GET | `/api/discussions/{id}` | Get discussion details |
| POST | `/api/discussions/{id}/memory` | Save discussion to memory |

### Request Parameters

**POST /api/ask & /api/submit:**
```json
{
  "provider": "kimi",           // Required: AI provider (9 options)
  "message": "Your question",   // Required: User message
  "model": "thinking",          // Optional: Specific model
  "wait": true,                 // Optional: Wait for completion
  "timeout": 120,               // Optional: Timeout in seconds
  "metadata": {}                // Optional: Custom metadata
}
```

---

## 📚 Documentation

### Core Documentation

- **[Gemini CLI Integration Guide](docs/GEMINI_CLI_INTEGRATION_GUIDE.md)** - Dual-path setup (v0.23.1)
- **[Gemini Auth Setup](docs/GEMINI_AUTH_SETUP.md)** - OAuth and API Key configuration (v0.23.1)
- **[Memory System Architecture](lib/memory/INTEGRATION_DESIGN.md)** - Full design
- **[Database Structure](lib/memory/DATABASE_STRUCTURE.md)** - Schema and queries
- **[Cloud Sync Guide](lib/memory/SYNC_QUICKSTART.md)** - Google Drive setup
- **[V1 vs V2 Comparison](lib/memory/V1_VS_V2.md)** - Memory evolution

### Test Reports (2026-02-06)

- **[Final Test Report](docs/CCB_FINAL_TEST_REPORT_2026-02-06.md)** - Full module integration test (8/9 providers passing)
- **[Issue Tracking](docs/CCB_TEST_ISSUES_2026-02-06.md)** - 6 issues fixed (100% fix rate)
- **[Retest Verification Report](docs/CCB_RETEST_REPORT_2026-02-06.md)** - Fix verification results

**Test Summary:**
- ✅ 8/9 Providers passing (89% success rate): Kimi, Qwen, DeepSeek, Gemini, iFlow, OpenCode, Qoder, Codex
- ✅ 6/6 local issues fixed (100% fix rate): UUID truncation, DeepSeek API, rate limiter deadlock, stats data, iFlow, Codex o4-mini
- ✅ 96% module test coverage: Gateway, State Store, Queue, Cache, Rate Limiter, Router, Memory v2
- ⏱️ Avg response time: 7-71s (tiered by provider)

### Additional Resources

- **[API Documentation](docs/API.md)** - Complete API reference
- **[Configuration Guide](docs/CONFIG.md)** - All configuration options
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment

---

## 🗺️ Roadmap

### v0.23.1 (Current) - Gemini CLI Integration ✅

- [x] **Dual-Path Integration** - Native CLI + Gateway automation modes
- [x] **Flexible Authentication** - OAuth (native) and API Key (Gateway) support
- [x] **Smart Switching** - Quick scripts to toggle between auth modes
- [x] **Documentation** - Complete integration and auth setup guides
- [x] **No Breaking Changes** - Preserve full native CLI functionality

### v0.23 (Previous) - LLM-Powered Memory ✅

- [x] **LLM Keyword Extraction** - Ollama + qwen2.5:7b semantic understanding
- [x] **Chinese Text Support** - Accurate keyword extraction for CJK languages
- [x] **Robust Fallback** - Auto-fallback to regex when Ollama unavailable
- [x] **FTS5 Optimization** - Trigram tokenizer for better Chinese full-text search
- [x] **Memory Integration** - LLM keywords + Heuristic retrieval = 95%+ accuracy
- [x] **Performance** - 1-2s local inference, minimal latency overhead

### v0.22 (Previous) - Heuristic Memory ✅

- [x] **Heuristic Retrieval** - Stanford Generative Agents-inspired αR + βI + γT scoring
- [x] **Importance Tracking** - User-rated and LLM-evaluated importance scores
- [x] **Access Logging** - Track memory access for recency calculation
- [x] **Ebbinghaus Decay** - Time-based forgetting curve implementation
- [x] **System 2 Enhancement** - Merge, abstract, forget operations
- [x] **ccb-consolidate CLI** - New consolidation management tool
- [x] **Configurable Weights** - `~/.ccb/heuristic_config.json`

### v0.21 (Previous) - Memory Enhancement ✅

- [x] **Memory Transparency** - Track injected memories per request
- [x] **Observations CRUD** - Manual memory management API
- [x] **LLM Consolidator** - AI-powered insight extraction
- [x] **Memory Config API** - Runtime configuration
- [x] **Skills Feedback Loop** - Rating-based recommendations
- [x] **Discussion Memory** - Persist multi-AI discussions
- [x] **CLI Enhancements** - trace, injections, export commands

### v0.20 (Previous) - Dual-System Memory ✅

- [x] **Context Saver** - System 1 instant archiving
- [x] **Memory Consolidator** - System 2 nightly processing
- [x] **ccb-mem CLI** - Unified memory management
- [x] **Security Hardening** - Path traversal protection
- [x] **Claude Provider** - Added as 9th provider

### v0.23 (Q2 2026) - Semantic Enhancement

- [ ] Qdrant vector database integration
- [ ] Semantic similarity search
- [ ] Multi-language embeddings
- [ ] Memory clustering

### v0.24 (Q3 2026) - Agent Autonomy

- [ ] Agent memory function calls (Letta mode)
- [ ] Structured memory blocks (core_memory)
- [ ] Self-updating agents
- [ ] Memory version control

### v0.25 (Q4 2026) - Team Collaboration

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

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

**Inspired by:**
- [Stanford Generative Agents](https://arxiv.org/pdf/2304.03442) - Heuristic retrieval formula
- [Awesome-AI-Memory](https://github.com/IAAR-Shanghai/Awesome-AI-Memory) - Memory system survey
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

- 🐛 Issues: [GitHub Issues](https://github.com/LeoLin990405/ai-router-ccb/issues)
- 📖 Docs: [Documentation](docs/)

---

<div align="center">

**Made with ❤️ by the CCB Team**

**[⬆ Back to Top](#-ccb-gateway)**

</div>
