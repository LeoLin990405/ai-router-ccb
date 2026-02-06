# Gemini Authentication Setup for CCB Gateway

## 问题背景

Gemini CLI 需要认证才能使用，否则每次调用都会卡住等待用户登录，导致：
- Health Check 不断触发 `gemini ping` 命令
- 进程累积（几十个僵尸进程）
- Gateway 性能下降

## 解决方案

### 方案 1：API Key 认证（推荐）

**优点**：无需 OAuth 流程，配置简单，不会过期

**步骤**：
```bash
# 1. 获取 API Key
# 访问 https://makersuite.google.com/app/apikey

# 2. 添加到 shell 配置
echo 'export GOOGLE_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc

# 3. 测试连接
gemini -m gemini-3-flash-preview -p "Hello"
```

### 方案 2：OAuth 认证

**优点**：更安全，支持自动刷新

**步骤**：
```bash
# 1. 登录（会打开浏览器）
gemini auth login

# 2. 授权完成后，credentials 保存在：
#    ~/.gemini/oauth_creds.json

# 3. 测试连接
gemini -m gemini-3-flash-preview -p "Hello"
```

### 方案 3：临时禁用 Gemini（如果不需要）

**步骤**：

编辑 `~/.local/share/codex-dual/config/gateway.yaml`：

```yaml
providers:
  gemini:
    enabled: false  # 🔥 禁用 Gemini

health_check:
  provider_overrides:
    gemini:
      enabled: false  # 🔥 禁用健康检查
```

## CCB Gateway 新特性

### 1. 自动认证预检查

新的启动脚本 `ccb-gateway-start.sh` 会在启动前：
- 检查 `GOOGLE_API_KEY` 是否设置
- 检查 OAuth credentials 是否存在
- 自动刷新过期的 OAuth token
- 提示认证方式

### 2. 健康检查配置

`config/gateway.yaml` 现在支持：

```yaml
health_check:
  enabled: true
  interval_s: 60  # 检查间隔（秒）
  timeout_s: 15   # 单次检查超时

  provider_overrides:  # 🔥 新功能：按 Provider 配置
    gemini:
      enabled: false  # 禁用 Gemini 健康检查
      reason: "Requires manual OAuth authentication"

    codex:
      enabled: false  # 禁用 Codex 健康检查

    kimi:
      enabled: true
      timeout_s: 10
```

**效果**：
- ✅ 不再向 Gemini 发送 `ping` 命令
- ✅ 避免僵尸进程累积
- ✅ 其他 Provider 正常健康检查

### 3. 快捷命令

```bash
# 启动 Gateway（带认证检查）
ccb-start

# 停止 Gateway（包括清理僵尸进程）
ccb-stop

# 查看日志
ccb-logs

# 查看状态
ccb-status
```

## 推荐工作流

### 首次设置

```bash
# 1. 配置 Gemini 认证（选择一种方式）
export GOOGLE_API_KEY="your-key"  # 方式 1
# 或
gemini auth login                 # 方式 2

# 2. 启动 Gateway
ccb-start

# 3. 测试
ccb-cli gemini "Hello"
```

### 日常使用

```bash
# 启动
ccb-start

# 使用
ccb-cli kimi "问题"
ccb-cli qwen "代码"

# 如需 Gemini（会自动刷新 token）
ccb-cli gemini "问题"

# 停止
ccb-stop
```

## 故障排查

### 问题 1：Gemini ping 进程不断累积

**原因**：Health Check 在向未认证的 Gemini 发送 ping

**解决**：
```bash
# 临时：杀死僵尸进程
pkill -9 -f "gemini.*ping"

# 永久：禁用 Gemini 健康检查
# 编辑 ~/.local/share/codex-dual/config/gateway.yaml
# 设置 health_check.provider_overrides.gemini.enabled = false
```

### 问题 2：Token 过期

**解决**：
```bash
# 自动刷新（在启动时）
ccb-start

# 手动刷新
python3 ~/.local/share/codex-dual/lib/gateway/gemini_auth.py

# 重新登录
gemini auth login
```

### 问题 3：Gateway 启动失败

**检查日志**：
```bash
tail -50 /tmp/ccb-gateway.log

# 常见原因：
# 1. 端口 8765 被占用 → ccb-stop 后重试
# 2. 配置文件语法错误 → 检查 gateway.yaml
# 3. Python 依赖缺失 → 重新安装 CCB
```

## 架构说明

```
┌─────────────────────────────────────────┐
│  ccb-gateway-start.sh                   │
│  ├─ [1] Check Gemini Auth               │
│  │   ├─ GOOGLE_API_KEY?                 │
│  │   └─ OAuth creds exist?              │
│  ├─ [2] Auto-refresh token              │
│  └─ [3] Start Gateway                   │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  gateway_server.py                      │
│  ├─ Load config/gateway.yaml            │
│  ├─ Init HealthChecker                  │
│  │   ├─ Read provider_overrides         │
│  │   ├─ Skip gemini/codex (disabled)    │
│  │   └─ Register kimi/qwen/deepseek     │
│  └─ Start periodic checks (60s)         │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  health_checker.py                      │
│  └─ Only ping enabled providers         │
│     ❌ Gemini (skipped)                  │
│     ❌ Codex (skipped)                   │
│     ✅ Kimi (check every 60s)            │
│     ✅ Qwen (check every 60s)            │
└─────────────────────────────────────────┘
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `bin/ccb-gateway-start.sh` | Gateway 启动脚本 |
| `config/gateway.yaml` | Gateway 配置文件 |
| `lib/gateway/gemini_auth.py` | Gemini Token 自动刷新 |
| `lib/gateway/health_checker.py` | 健康检查逻辑 |
| `lib/gateway/gateway_server.py` | Gateway 主程序 |

## 更新日志

- **2026-02-06**:
  - ✅ 添加健康检查配置支持
  - ✅ 支持 provider_overrides（按 Provider 禁用）
  - ✅ 创建 ccb-gateway-start.sh 启动脚本
  - ✅ 默认禁用 Gemini/Codex 健康检查
  - ✅ 增加检查间隔到 60 秒
