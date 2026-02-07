# CC Switch Integration for CCB Gateway

## 概述

CC Switch 集成为 CCB Gateway 提供了 Provider 管理和并行测试功能。通过集成 CC Switch 数据库，CCB 可以：

- 🔀 **故障转移队列** - 基于优先级的自动 Provider 切换
- 📊 **Provider 状态监控** - 实时查看所有 Provider 的健康状况
- ⚡ **并行测试** - 同时向多个 Provider 发送相同请求
- 🎯 **性能对比** - 比较不同 Provider 的响应速度和质量

## 架构

### 组件

| 组件 | 文件位置 | 功能 |
|------|----------|------|
| **CCSwitch 模块** | `lib/gateway/cc_switch.py` | 核心集成逻辑 |
| **Gateway API 端点** | `lib/gateway/gateway_api.py` | REST API 接口 |
| **CLI 工具** | `bin/ccb-cc-switch` | 命令行交互 |
| **CC Switch 数据库** | `~/.cc-switch/cc-switch.db` | Provider 配置存储 |

### 数据流

```
用户命令 → ccb-cc-switch CLI → Gateway API → CCSwitch 模块 → CC Switch DB
                                      ↓
                              并行调用多个 Provider
                                      ↓
                              聚合结果并返回
```

## 安装

CC Switch 集成已内置于 CCB Gateway，无需额外安装。

**前置条件：**
- CCB Gateway v0.23.1+
- CC Switch 数据库位于 `~/.cc-switch/cc-switch.db`

## 使用

### CLI 命令

#### 1. 获取 Provider 状态

```bash
ccb-cc-switch status
```

**输出示例：**
```
📊 CC Switch Status
   Total Providers: 5
   Active Providers: 3

🔄 Failover Queue:
   1. 反重力
   2. AiGoCode-优质逆向
   3. Claude Official

📋 Provider Details:
   ✓ 反重力
      Priority: 100, Failures: 0
      Last Success: 2026-02-07 01:30:45
   ✓ AiGoCode-优质逆向
      Priority: 90, Failures: 1
      Last Success: 2026-02-07 01:25:12
   ✗ Provider X
      Priority: 50, Failures: 5
```

#### 2. 重新加载 Provider

当更新 CC Switch 数据库后，使用此命令重新加载：

```bash
ccb-cc-switch reload
```

**输出：**
```
✓ Reloaded CC Switch providers
  Total: 5
  Active: 3
```

#### 3. 获取故障转移队列

仅显示故障转移队列（按优先级排序）：

```bash
ccb-cc-switch queue
```

**输出：**
```
🔄 Failover Queue (3 providers):
   1. 反重力
   2. AiGoCode-优质逆向
   3. Claude Official
```

#### 4. 并行测试 Provider

**测试所有活跃 Provider：**
```bash
ccb-cc-switch test "用一句话解释递归"
```

**测试指定 Provider：**
```bash
ccb-cc-switch test "Explain recursion in one sentence" \
  -p "反重力" \
  -p "AiGoCode-优质逆向" \
  -p "Claude Official"
```

**使用自定义超时：**
```bash
ccb-cc-switch test "Complex question that may take longer..." -t 120
```

**输出示例：**
```
🧪 Testing providers in parallel...
   Message: 用一句话解释递归

📊 Test Results (ID: cc-parallel-1738906789000)
   Total Time: 3456ms
   Success: 3, Failed: 0

🏆 Fastest: 反重力 (1234ms)

📋 Provider Results:
   ✓ 反重力 (1234ms)
      Tokens: 128
      Response: 递归是函数调用自身的编程技术，通过将问题分解为更小的子问题来解决。

   ✓ AiGoCode-优质逆向 (2345ms)
      Tokens: 95
      Response: 递归就是函数自己调用自己，直到满足终止条件。

   ✓ Claude Official (2567ms)
      Tokens: 112
      Response: Recursion is a technique where a function calls itself to solve smaller instances of the same pro...
```

### API 端点

#### 1. 获取 Provider 状态

**请求：**
```bash
curl http://localhost:8765/api/cc-switch/status | jq .
```

**响应：**
```json
{
  "total_providers": 5,
  "active_providers": 3,
  "failover_queue": ["反重力", "AiGoCode-优质逆向", "Claude Official"],
  "providers": [
    {
      "id": 1,
      "name": "反重力",
      "priority": 100,
      "status": "active",
      "last_success": "2026-02-07 01:30:45",
      "fail_count": 0
    }
  ]
}
```

#### 2. 重新加载 Provider

**请求：**
```bash
curl -X POST http://localhost:8765/api/cc-switch/reload | jq .
```

**响应：**
```json
{
  "reloaded": true,
  "total_providers": 5,
  "active_providers": 3
}
```

#### 3. 获取故障转移队列

**请求：**
```bash
curl http://localhost:8765/api/cc-switch/failover-queue | jq .
```

**响应：**
```json
{
  "failover_queue": ["反重力", "AiGoCode-优质逆向", "Claude Official"],
  "count": 3
}
```

#### 4. 并行测试 Provider

**请求：**
```bash
curl -X POST http://localhost:8765/api/cc-switch/parallel-test \
  -H "Content-Type: application/json" \
  -d '{
    "message": "用一句话解释递归",
    "providers": ["反重力", "AiGoCode-优质逆向"],
    "timeout_s": 60
  }' | jq .
```

**响应：**
```json
{
  "request_id": "cc-parallel-1738906789000",
  "message": "用一句话解释递归",
  "providers": ["反重力", "AiGoCode-优质逆向"],
  "results": {
    "反重力": {
      "provider_name": "反重力",
      "success": true,
      "response": "递归是函数调用自身的编程技术...",
      "latency_ms": 1234.56,
      "tokens_used": 128,
      "timestamp": 1738906789.123
    },
    "AiGoCode-优质逆向": {
      "provider_name": "AiGoCode-优质逆向",
      "success": true,
      "response": "递归就是函数自己调用自己...",
      "latency_ms": 2345.67,
      "tokens_used": 95,
      "timestamp": 1738906789.234
    }
  },
  "total_latency_ms": 2345.67,
  "success_count": 2,
  "failure_count": 0,
  "fastest_provider": "反重力",
  "fastest_latency_ms": 1234.56
}
```

## Python API

### CCSwitch 类

```python
from lib.gateway.cc_switch import CCSwitch

# 初始化
cc_switch = CCSwitch()  # 默认使用 ~/.cc-switch/cc-switch.db
# 或指定数据库路径
cc_switch = CCSwitch(db_path="/path/to/cc-switch.db")

# 获取状态
status = cc_switch.get_status()

# 获取活跃 Provider
active_providers = cc_switch.get_active_providers()

# 获取故障转移队列
queue = cc_switch.get_failover_queue()

# 重新加载
cc_switch.reload()
```

### 并行测试

```python
import asyncio
from lib.gateway.cc_switch import CCSwitch

async def test_providers():
    cc_switch = CCSwitch()

    # 测试所有活跃 Provider
    result = await cc_switch.parallel_test(
        message="用一句话解释递归"
    )

    # 测试指定 Provider
    result = await cc_switch.parallel_test(
        message="Explain recursion",
        providers=["反重力", "AiGoCode-优质逆向"],
        timeout_s=60.0
    )

    print(f"Success: {result.success_count}/{len(result.providers)}")
    print(f"Fastest: {result.fastest_provider} ({result.fastest_latency_ms:.0f}ms)")

    return result.to_dict()

# 运行
asyncio.run(test_providers())
```

## 用例

### 1. Provider 可用性检测

在执行关键任务前，快速检测哪些 Provider 可用：

```bash
ccb-cc-switch test "ping" -t 10
```

### 2. 性能基准测试

对比不同 Provider 的响应速度：

```bash
ccb-cc-switch test "写一个快速排序算法" \
  -p "反重力" \
  -p "AiGoCode-优质逆向" \
  -p "Claude Official" \
  -t 120
```

### 3. 质量对比

获取多个 Provider 的响应，人工选择最佳答案：

```bash
ccb-cc-switch test "如何优化 React 应用的性能？" -t 60
```

### 4. 故障转移验证

验证故障转移队列是否正确配置：

```bash
ccb-cc-switch status
ccb-cc-switch queue
```

## 最佳实践

### 1. 优先级设置

在 CC Switch 数据库中合理设置 Provider 优先级：

- **100+**: 最高质量 Provider（如官方 API）
- **80-99**: 高质量备用 Provider
- **50-79**: 一般备用 Provider
- **<50**: 仅在紧急情况下使用

### 2. 超时配置

根据任务复杂度设置超时：

- **简单问答**: 30s
- **代码生成**: 60s
- **复杂推理**: 120s+

### 3. Provider 选择

并行测试时选择合适的 Provider：

- **快速任务**: 只测试快速 Provider
- **质量优先**: 测试所有高优先级 Provider
- **全面对比**: 测试所有活跃 Provider

### 4. 结果解析

从并行测试结果中提取有用信息：

```python
result = await cc_switch.parallel_test(message)

# 获取最快的成功响应
if result.fastest_provider:
    fastest_response = result.results[result.fastest_provider].response

# 获取所有成功响应（供人工选择）
successful_responses = {
    name: r.response
    for name, r in result.results.items()
    if r.success
}

# 计算平均延迟
avg_latency = sum(
    r.latency_ms for r in result.results.values()
) / len(result.results)
```

## 故障排查

### 问题：数据库未找到

**错误：**
```
⚠️  CC Switch database not found: ~/.cc-switch/cc-switch.db
```

**解决：**
1. 确认 CC Switch 已安装
2. 检查数据库路径是否正确
3. 手动创建 `~/.cc-switch/` 目录

### 问题：所有 Provider 测试失败

**错误：**
```
success_count: 0
failure_count: 3
```

**排查：**
1. 检查 API Key 是否有效：`ccb-check-auth`
2. 检查网络连接
3. 查看具体错误信息：每个 Provider 的 `error` 字段
4. 增加超时时间：`-t 120`

### 问题：Gateway 未运行

**错误：**
```
✖ Failed to get status: Connection refused
```

**解决：**
```bash
# 检查 Gateway 状态
ccb-gateway status

# 启动 Gateway
ccb-gateway-start.sh
```

## 性能指标

### 并行测试性能

- **并发数**: 最多同时测试所有活跃 Provider
- **总延迟**: 由最慢的 Provider 决定
- **内存开销**: 约 ~50KB/Provider
- **超时处理**: 每个 Provider 独立超时

### 示例测试结果

测试 3 个 Provider，消息："用一句话解释递归"

| Provider | 延迟 | Tokens | 成功率 |
|----------|------|--------|--------|
| 反重力 | 1.2s | 128 | 100% |
| AiGoCode | 2.3s | 95 | 100% |
| Claude | 2.6s | 112 | 100% |

**总延迟**: 2.6s（并行执行）
**如果串行**: 1.2s + 2.3s + 2.6s = 6.1s

**性能提升**: **2.35x**

## 未来增强

### v0.24 计划

- [ ] Web UI 集成 - CC Switch 状态面板
- [ ] 自动故障转移 - Gateway 自动切换失败的 Provider
- [ ] 历史记录 - 记录并行测试历史
- [ ] 质量评分 - 自动评估响应质量
- [ ] A/B 测试 - 对比不同 Provider 的长期表现

### v0.25 计划

- [ ] 机器学习路由 - 基于历史数据智能选择 Provider
- [ ] 成本优化 - 根据 Token 价格选择 Provider
- [ ] 自动重试 - 失败时自动使用故障转移队列
- [ ] 负载均衡 - 根据 Provider 负载分配请求

## 相关文档

- [CCB Gateway README](../README.md)
- [Gateway API 文档](../lib/gateway/gateway_api.py)
- [CLI 工具文档](../bin/ccb-cc-switch)
- [CC Switch 原理](https://github.com/your-repo/cc-switch)

## 更新日志

### v0.23.1 (2026-02-07)

**新增：**
- ✨ CC Switch 集成模块 (`lib/gateway/cc_switch.py`)
- ✨ Gateway API 端点（4 个新端点）
- ✨ `ccb-cc-switch` CLI 工具
- 📚 完整文档和使用示例

**功能：**
- 🔀 Provider 状态监控
- ⚡ 并行 Provider 测试
- 📊 性能对比和基准测试
- 🎯 故障转移队列管理

---

**作者**: CCB Team
**日期**: 2026-02-07
**版本**: v0.23.1
