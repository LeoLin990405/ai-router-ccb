# Gemini CLI 集成指南

**更新日期**: 2026-02-06
**版本**: v0.23.1

## 问题背景

Gemini CLI 在使用过程中经常遇到认证跳转问题（OAuth token 过期导致重复跳转到浏览器登录），影响使用体验和自动化流程。

## 解决方案架构

采用 **双路径集成** 策略，让用户根据场景选择最佳方式：

### 方案 A: 独立使用 Gemini CLI（交互式）

**用途**: 日常手动使用，需要完整交互体验

```bash
gemini                    # 启动交互式 CLI
gemini "直接提问"          # 快速提问（单次）
```

**特点**:
- ✅ 保留原生 CLI 完整功能
- ✅ 支持交互式对话
- ⚠️ 可能遇到认证跳转

### 方案 B: CCB Gateway 集成（自动化）

**用途**: CCB 系统调用、自动化脚本、批量任务

```bash
ccb-cli gemini 3f "问题"      # Gemini 3 Flash
ccb-cli gemini 3p "问题"      # Gemini 3 Pro
ccb-cli gemini 2.5f "问题"    # Gemini 2.5 Flash
```

**特点**:
- ✅ 通过 Gateway 统一认证（使用 API Key）
- ✅ 避免 OAuth 跳转问题
- ✅ 支持缓存、监控、重试
- ✅ 集成到 CCB 多 AI 协作系统

## 配置方式

### 1. 反重力 API 配置（推荐）

在 `~/.zshrc` 中设置 API Key：

```bash
# 反重力代理 API 配置
export ANTHROPIC_API_KEY="your-api-key-here"
export ANTHROPIC_BASE_URL="https://api.aigocode.com"
```

### 2. Gemini CLI OAuth 配置（备选）

```bash
# 切换到 OAuth 模式
~/.gemini/switch-to-oauth.sh

# 重置 OAuth token
gemini auth
```

### 3. 快速切换脚本

```bash
# OAuth 模式（交互式使用）
~/.gemini/switch-to-oauth.sh

# API Key 模式（自动化使用）
~/.gemini/switch-to-apikey.sh
```

## CCB 系统集成

### Claude Code 中使用

在 Claude Code 会话中，所有 Gemini 调用自动通过 Gateway：

```
User: "ask gemini to help me with React"
Claude: (自动调用 ccb-cli gemini 3f "help me with React")
```

### CLAUDE.md 配置

全局配置文件 `~/.claude/CLAUDE.md` 中已包含智能路由规则：

```yaml
任务类型 → Provider 映射:
  - 前端/React/Vue/CSS → gemini 3f (首选)
  - 算法/推理 → codex o3
  - 中文/长文本 → kimi
  - ...
```

## 常见问题

### Q1: Gemini CLI 一直跳转到浏览器登录？

**A**: 使用 CCB Gateway 方式调用，避免 OAuth 问题：

```bash
ccb-cli gemini 3f "你的问题"
```

### Q2: 如何在脚本中使用 Gemini？

**A**: 使用 `ccb-submit` 异步模式，避免超时：

```bash
REQUEST_ID=$(ccb-submit gemini "复杂问题")
sleep 30
ccb-query get $REQUEST_ID
```

### Q3: API Key 配额用完怎么办？

**A**:
1. 检查反重力 App 中的配额
2. 临时切换到 OAuth 模式：`~/.gemini/switch-to-oauth.sh`
3. 等待配额重置（通常 24 小时）

### Q4: 如何查看 Gateway 状态？

**A**:
```bash
curl http://localhost:8765/api/health
ccb-gateway status
```

## 性能对比

| 方式 | 认证方式 | 响应时间 | 适用场景 |
|------|----------|----------|----------|
| Gemini CLI (OAuth) | OAuth 浏览器登录 | 60-180s | 手动交互 |
| CCB Gateway (API Key) | 统一 API Key | 60-180s | 自动化、脚本 |
| CCB Gateway (缓存命中) | - | <1s | 重复请求 |

## 更新日志

### v0.23.1 (2026-02-06)

- 🔧 移除 Gemini 函数覆盖，恢复原生 CLI 体验
- 📝 更新 `~/.zshrc` 配置说明
- 📖 创建本集成指南文档
- ✅ 支持双路径使用（独立 CLI + CCB Gateway）

### v0.23 (2026-02-06)

- ✨ Gemini CLI 通过 CCB Gateway 集成
- 🔐 支持 OAuth 和 API Key 双认证方式
- 🚀 自动 sync-to-async 切换机制
- 💾 LLM 关键词提取（Ollama + qwen2.5:7b）

## 相关文档

- [GEMINI_AUTH_SETUP.md](./GEMINI_AUTH_SETUP.md) - 详细认证配置
- [CHANGELOG_2026-02-06.md](../CHANGELOG_2026-02-06.md) - 完整变更日志
- [README.md](../README.md) - CCB 系统总览

## 支持

如遇问题，请检查：
1. Gateway 是否运行：`curl http://localhost:8765/api/health`
2. API Key 配额：反重力 App 查看
3. 日志文件：`tail -f /tmp/ccb-gateway.log`
