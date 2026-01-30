# AI Router CCB - Intelligent Multi-AI Collaboration Platform

> **An optimized fork of [bfly123/claude_code_bridge](https://github.com/bfly123/claude_code_bridge) with intelligent task routing**
>
> Special thanks to the original author **bfly123** and the community for creating this amazing multi-AI collaboration framework.

**English** | [中文说明](README_zh.md)

---

## About This Project

**AI Router CCB** is a unified AI collaboration platform that intelligently routes tasks to the optimal AI provider based on task type, keywords, and file patterns.

### Core Features
- **Intelligent Routing**: Automatically selects the best AI provider for each task
- **Magic Keywords**: Special keywords (`@deep`, `@review`, `@all`, etc.) trigger enhanced behaviors
- **Task Tracking**: SQLite-backed task management with status tracking
- **Performance Analytics**: Track provider latency, success rates, and token usage
- **Smart Caching**: Cache responses to reduce redundant requests
- **Auto Retry**: Automatic retry with exponential backoff and provider fallback
- **Multi-Provider Queries**: Query multiple providers simultaneously with result aggregation
- **Batch Processing**: Process multiple tasks in parallel
- **Web Dashboard**: Real-time monitoring and management UI
- **9 AI Providers**: Claude, Codex, Gemini, OpenCode, DeepSeek, Droid, iFlow, Kimi, Qwen
- **Unified Interface**: Consistent command pattern across all providers
- **Health Monitoring**: Real-time provider status checking
- **Configurable Rules**: YAML-based routing configuration
- **Context7 Integration**: Optional documentation lookup to reduce AI hallucinations

### Contributors
- **Leo** ([@LeoLin990405](https://github.com/LeoLin990405)) - Project lead & integration
- **Claude** (Anthropic Claude Opus 4.5) - Architecture design & code optimization
- **Codex** (OpenAI GPT-5.2 Codex) - Script development & debugging

---

## Intelligent Task Routing

The core innovation of AI Router CCB is its intelligent routing engine, inspired by [Nexus Router](https://github.com/grafbase/nexus).

### Quick Start
```bash
# Smart routing - auto-selects best provider
ccb ask "添加 React 组件"        # → gemini (frontend)
ccb ask "设计 API 接口"          # → codex (backend)
ccb ask "分析这个算法的复杂度"    # → deepseek (reasoning)

# Magic keywords - trigger special behaviors
ccb ask "@deep analyze this algorithm"   # → deepseek (forced)
ccb ask "@review check this code"        # → gemini (code review mode)
ccb ask "@all what is the best approach" # → multi-provider query

# Show routing decision without executing
ccb route "帮我审查这段代码"

# Check all provider health status
ccb health

# List available magic keywords
ccb magic

# Force specific provider
ccb ask -p claude "任何问题"

# Route based on file context
ccb route -f src/components/Button.tsx "修改这个文件"

# Task tracking
ccb ask --track "analyze this code"  # Creates tracked task
ccb tasks list                       # List all tasks
ccb tasks stats                      # Show task statistics
```

### Routing Rules

| Task Type | Keywords | File Patterns | Provider |
|-----------|----------|---------------|----------|
| Frontend | react, vue, component, 前端, 组件 | `*.tsx`, `*.vue`, `components/**` | gemini |
| Backend | api, endpoint, 后端, 接口 | `api/**`, `routes/**`, `services/**` | codex |
| Architecture | design, architect, 设计, 架构 | - | claude |
| Reasoning | analyze, reason, 分析, 推理, 算法 | - | deepseek |
| Code Review | review, check, 审查, 检查 | - | gemini |
| Quick Query | what, how, why, 什么, 怎么 | - | claude |

### Magic Keywords

Magic keywords trigger special routing behaviors when detected in your message:

| Keyword | Action | Provider | Description |
|---------|--------|----------|-------------|
| `@search` | web_search | gemini | Trigger web search |
| `@docs` | context7_lookup | claude | Query Context7 documentation |
| `@deep` | deep_reasoning | deepseek | Force deep reasoning mode |
| `@review` | code_review | gemini | Force code review mode |
| `@all` | multi_provider | claude,gemini,codex | Query multiple providers |
| `smartroute` | full_auto | - | Enable all smart features |

```bash
# Examples
ccb ask "@deep analyze the time complexity of this algorithm"
ccb ask "@review check this code for security issues"
ccb ask "@all what's the best approach for this problem"
ccb route "smartroute optimize this function"
```

---

## Performance Analytics

Track and analyze provider performance over time:

```bash
# View all provider statistics (last 24 hours)
ccb stats

# View specific provider stats
ccb stats --provider claude --hours 48

# Show recent requests
ccb stats recent --limit 20

# Get summary report
ccb stats summary

# Find best performing provider
ccb stats best

# Export data
ccb stats --export csv > performance.csv
ccb stats --export json > performance.json

# Cleanup old data
ccb stats cleanup --days 30
```

### Tracked Metrics
- **Latency**: Response time in milliseconds
- **Success Rate**: Percentage of successful requests
- **Token Usage**: Input/output token counts (when available)
- **Request Volume**: Total requests per provider

---

## Smart Caching

Reduce redundant requests with intelligent response caching:

```bash
# View cache statistics
ccb cache stats

# List cached entries
ccb cache list --limit 20

# Get specific cache entry
ccb cache get <key>

# Clear all cache
ccb cache clear

# Cleanup expired entries
ccb cache cleanup
```

### Cache Features
- **Automatic Caching**: Responses cached automatically (configurable TTL)
- **Hit Rate Tracking**: Monitor cache effectiveness
- **Provider-Specific**: Cache entries tagged by provider
- **Disable Per-Request**: Use `--no-cache` flag to bypass

```bash
# Bypass cache for fresh response
ccb ask --no-cache "what is the current time"
```

---

## Auto Retry & Fallback

Automatic retry with exponential backoff and provider fallback chains:

```bash
# Enable retry (default)
ccb ask --retry "your question"

# Disable retry
ccb ask --no-retry "your question"

# Custom retry attempts
ccb ask --max-retries 5 "your question"
```

### Fallback Chains
When a provider fails, CCB automatically tries fallback providers:

| Primary | Fallback Chain |
|---------|----------------|
| claude | gemini → codex |
| gemini | claude → codex |
| codex | claude → gemini |
| deepseek | claude → gemini |
| kimi | claude → qwen |
| qwen | claude → kimi |

---

## Multi-Provider Queries

Query multiple providers simultaneously and aggregate results:

```bash
# Query all default providers (claude, gemini, codex)
ccb ask "@all what is the best approach"

# Specify providers
ccb ask --multi --providers claude,gemini,deepseek "analyze this"

# Different aggregation strategies
ccb ask --multi --strategy all "your question"      # Show all results
ccb ask --multi --strategy merge "your question"   # Merge results
ccb ask --multi --strategy compare "your question" # Side-by-side comparison
ccb ask --multi --strategy first_success "question" # First successful response
```

---

## Batch Processing

Process multiple tasks in parallel with SQLite persistence:

```bash
# From file (one message per line)
ccb batch run -f tasks.txt

# From command line
ccb batch run "msg1" "msg2" "msg3"

# From stdin
echo -e "task1\ntask2\ntask3" | ccb batch run --stdin

# With specific provider
ccb batch run -p claude -f tasks.txt

# Control concurrency
ccb batch run -c 10 -f tasks.txt  # 10 concurrent tasks

# Output results to file
ccb batch run -f tasks.txt -o results.txt

# Check job status
ccb batch status <job_id>

# List recent jobs
ccb batch list

# Cancel a job
ccb batch cancel <job_id>

# Clean up old jobs
ccb batch cleanup --hours 24

# Delete a specific job
ccb batch delete <job_id>
```

### Batch Features
- **SQLite Persistence**: Jobs survive process restarts
- **Parallel Execution**: Configurable concurrency
- **Progress Tracking**: Real-time status updates
- **Job Management**: List, cancel, cleanup, delete

---

## Web Dashboard

Real-time monitoring and management through a web interface:

```bash
# Start web server (default: localhost:8080)
ccb web

# Custom port
ccb web --port 9000

# Allow external access
ccb web --host 0.0.0.0

# Don't auto-open browser
ccb web --no-browser
```

### Dashboard Features
- **Overview**: Total requests, success rate, cache stats
- **Provider Performance**: Latency, success rate per provider
- **Task Management**: View and manage tasks
- **Cache Management**: View and clear cache
- **Health Status**: Real-time provider health checks

**Note**: Requires `pip install fastapi uvicorn jinja2`

### Configuration
Edit `~/.ccb_config/unified-router.yaml` to customize routing rules:
```yaml
routing_rules:
  - name: frontend
    priority: 10
    patterns:
      - "**/components/**"
      - "**/*.tsx"
    keywords:
      - react
      - vue
      - 前端
    provider: gemini

# Task tracking configuration
task_tracking:
  enabled: true
  db_path: ~/.ccb_config/tasks.db
  auto_cleanup: true
  cleanup_hours: 24

# Magic keywords configuration
magic_keywords:
  enabled: true
  keywords:
    - keyword: "@deep"
      action: deep_reasoning
      provider: deepseek
      description: "Force deep reasoning mode"
```

---

## Task Tracking System

Track and manage tasks across multiple AI providers:

```bash
# Create a tracked task
ccb ask --track "analyze this code"
# Output: [Task] Created task: abc123

# List all tasks
ccb tasks list
ccb tasks list --status running
ccb tasks list --provider deepseek

# Get task details
ccb tasks get abc123

# Cancel a task
ccb tasks cancel abc123

# View statistics
ccb tasks stats

# Cleanup old tasks
ccb tasks cleanup --hours 24
```

### Task Status Lifecycle
```
pending → running → completed
                  → failed
                  → cancelled
```

---

## Supported Providers

| Provider | Command | Ping | Description |
|----------|---------|------|-------------|
| Claude | `lask` | `lping` | General purpose, architecture, quick queries |
| Codex | `cask` | `cping` | Backend, API, systems programming |
| Gemini | `gask` | `gping` | Frontend, code review, multimodal |
| OpenCode | `oask` | `oping` | General coding assistance |
| DeepSeek | `dskask` | `dskping` | Deep reasoning, algorithms, optimization |
| Droid | `dask` | `dping` | Autonomous task execution |
| iFlow | `iask` | `iping` | Workflow automation |
| Kimi | `kask` | `kping` | Chinese language, long context |
| Qwen | `qask` | `qping` | Multilingual, general purpose |

---

## Installation

### Prerequisites
- [WezTerm](https://wezfurlong.org/wezterm/) (recommended) or tmux
- Provider CLIs installed:
  - `claude` (Anthropic)
  - `codex` (OpenAI)
  - `gemini` (Google)
  - Others as needed

### Install
```bash
# Clone this repository
git clone https://github.com/LeoLin990405/ai-router-ccb.git ~/.local/share/codex-dual

# Run installer
cd ~/.local/share/codex-dual
./install.sh
```

### Environment Variables
Add to your `~/.zshrc` or `~/.bashrc`:
```bash
# CCB Core
export CCB_SIDECAR_AUTOSTART=1
export CCB_SIDECAR_DIRECTION=right
export CCB_CLI_READY_WAIT_S=20

# DeepSeek
export CCB_DSKASKD_QUICK_MODE=1
export CCB_DSKASKD_ALLOW_NO_SESSION=1

# Kimi - CLI starts slowly
export CCB_KASKD_STARTUP_WAIT_S=25

# iFlow (GLM) - Model responds slowly
export CCB_IASKD_STARTUP_WAIT_S=30
```

---

## Usage

### From Claude Code
```bash
# Using prefixes
@codex review this code
@gemini search for latest React docs
@deepseek 分析这个算法

# Using ask command
ask codex "explain this function"
ask gemini "what is the weather today"
```

### Direct Commands
```bash
# Ask questions
cask "review this code"
gask "search for documentation"
dskask "分析代码"

# Check connectivity
cping
gping
dskping

# Get pending replies
cpend
gpend
dskpend
```

### CCB Commands
```bash
# Start providers
ccb codex gemini opencode

# Intelligent routing
ccb ask "your question"
ccb ask --track "tracked question"  # With task tracking
ccb ask --no-cache "fresh query"    # Bypass cache
ccb ask --retry "reliable query"    # With auto-retry
ccb route "show routing only"
ccb health
ccb magic                           # List magic keywords

# Task management
ccb tasks list
ccb tasks get <task_id>
ccb tasks stats
ccb tasks cleanup

# Performance analytics
ccb stats                           # View provider stats
ccb stats --provider claude         # Specific provider
ccb stats best                      # Best performing provider

# Cache management
ccb cache stats                     # Cache statistics
ccb cache list                      # List entries
ccb cache clear                     # Clear cache

# Batch processing
ccb batch run -f tasks.txt          # Process batch
ccb batch status <job_id>           # Check status
ccb batch list                      # List jobs

# Web dashboard
ccb web                             # Start web UI

# Documentation lookup (requires Context7)
ccb docs react "how to use hooks"
ccb docs pandas "dataframe operations"

# Management
ccb kill
ccb version
ccb update
```

---

## File Structure
```
~/.local/share/codex-dual/
├── bin/                    # Command scripts (ask/ping/pend)
│   ├── ccb-ask            # Intelligent routing CLI
│   ├── ccb-tasks          # Task management CLI
│   ├── ccb-stats          # Performance analytics CLI
│   ├── ccb-cache          # Cache management CLI
│   ├── ccb-batch          # Batch processing CLI
│   ├── ccb-web            # Web dashboard CLI
│   ├── ccb-docs           # Documentation lookup CLI
│   ├── cask, gask, ...    # Provider ask commands
│   └── cping, gping, ...  # Provider ping commands
├── lib/                    # Library modules
│   ├── unified_router.py  # Routing engine with magic keywords
│   ├── task_tracker.py    # Task tracking system
│   ├── performance_tracker.py  # Performance analytics
│   ├── response_cache.py  # Smart caching system
│   ├── retry_policy.py    # Auto retry with fallback
│   ├── multi_provider.py  # Multi-provider execution
│   ├── batch_processor.py # Batch task processing
│   ├── web_server.py      # Web dashboard server
│   ├── context7_client.py # Context7 integration
│   └── *_daemon.py        # Provider daemons
├── config/                 # Configuration templates
├── ccb                     # Main CCB binary
└── install.sh              # Installer script

~/.ccb_config/
├── unified-router.yaml    # Routing configuration
├── tasks.db               # Task tracking database
├── performance.db         # Performance metrics database
├── cache.db               # Response cache database
└── .*-session             # Provider session files
```

---

## Troubleshooting

### Provider not responding
1. Check connectivity: `<provider>ping`
2. Verify CLI is installed and authenticated
3. Check environment variables

### Routing not working as expected
1. Check routing decision: `ccb route "your message"`
2. Review `~/.ccb_config/unified-router.yaml`
3. Use `-v` flag for verbose output: `ccb ask -v "message"`

### Sidecar not opening
1. Ensure WezTerm is running
2. Check `CCB_SIDECAR_AUTOSTART=1`
3. Verify `CCB_SIDECAR_DIRECTION` is set

---

## Acknowledgements

This project would not be possible without:

- **[bfly123](https://github.com/bfly123)** - Original author of claude_code_bridge. Thank you for creating this innovative multi-AI collaboration framework!
- **[Grafbase / Nexus Router](https://github.com/grafbase/nexus)** - Inspiration for the Unified Router's intelligent task routing architecture. Their work on AI gateway and provider routing influenced our implementation.
- **[code-yeongyu / oh-my-opencode](https://github.com/code-yeongyu/oh-my-opencode)** - Inspiration for agent orchestration patterns, multi-agent architecture, and background task execution. Their Sisyphus agent and magic keyword concepts influenced our design.
- **The claude_code_bridge community** - For feedback and contributions
- **Anthropic** - For Claude and Claude Code
- **OpenAI** - For Codex
- **Google** - For Gemini
- **DeepSeek, Kimi, Qwen, iFlow teams** - For their excellent AI assistants

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Contributing

Issues and PRs are welcome! Please feel free to:
- Report bugs
- Suggest new features
- Add support for more providers
- Improve documentation

---

*Built with ❤️ by Leo, Claude, and Codex*
