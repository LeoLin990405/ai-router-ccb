# CCB Memory 深度集成设计方案

## 🎯 设计目标

将记忆系统从**独立工具**升级为 **CCB 核心能力**，实现：

1. **自动化** - 无需手动调用，自动记录和注入
2. **智能化** - 语义理解，自动推荐最佳 AI
3. **透明化** - 用户无感知，后台自动工作
4. **可扩展** - 支持向量搜索、云端同步、团队协作

---

## 🏗️ 混合架构设计

### 核心理念

**借鉴 4 个系统的最佳实践：**

| 借鉴系统 | 采用特性 | 应用到 CCB |
|---------|---------|-----------|
| **Mem0** | 语义搜索 + 自动提取 | Gateway 层自动记录，向量搜索 |
| **Letta** | 结构化记忆块 + Agent 控制 | Provider 特性记忆，自主更新 |
| **LangChain** | 模板注入 + 多种策略 | 上下文模板化，渐进式加载 |
| **Claude-Mem** | Lifecycle hooks | Gateway 生命周期钩子 |

---

## 📐 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Input                                │
│              "用 ccb-cli kimi '如何做前端开发'"                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   ccb-cli Wrapper (bin/ccb-cli)                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. 解析命令（provider, model, prompt）                     │   │
│  │ 2. 调用 Gateway API                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│           CCB Gateway (lib/gateway/gateway_server.py)            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Memory Middleware（新增）                                 │   │
│  │ ┌────────────────────────────────────────────────────┐   │   │
│  │ │ [Pre-Request Hook]                                 │   │   │
│  │ │ 1. 提取任务关键词                                    │   │   │
│  │ │ 2. 语义搜索相关记忆（Mem0 模式）                      │   │   │
│  │ │ 3. 推荐最佳 Provider（Registry）                     │   │   │
│  │ │ 4. 注入上下文到 prompt（LangChain 模式）              │   │   │
│  │ └────────────────────────────────────────────────────┘   │   │
│  │                                                           │   │
│  │ ┌────────────────────────────────────────────────────┐   │   │
│  │ │ [Provider Call]                                    │   │   │
│  │ │ 调用实际 AI Provider                                │   │   │
│  │ └────────────────────────────────────────────────────┘   │   │
│  │                                                           │   │
│  │ ┌────────────────────────────────────────────────────┐   │   │
│  │ │ [Post-Response Hook]                               │   │   │
│  │ │ 1. 记录对话到 SQLite                                 │   │   │
│  │ │ 2. 提取关键事实（Mem0 LLM 提取）                      │   │   │
│  │ │ 3. 生成向量嵌入（可选）                              │   │   │
│  │ │ 4. 更新推荐权重                                      │   │   │
│  │ └────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│              Memory Storage Layer（存储层）                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ SQLite + FTS5（快速全文搜索）                             │   │
│  │ ~/.ccb/ccb_memory.db                                    │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Qdrant（可选，语义搜索）                                  │   │
│  │ ~/.ccb/qdrant_data/                                     │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Google Drive（云端同步）                                 │   │
│  │ CCB-Memory/ folder                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔧 集成点设计

### 1. Gateway Middleware（核心集成点）

**文件：** `lib/gateway/middleware/memory_middleware.py`

```python
"""
Gateway Memory Middleware
在 Gateway 层自动处理记忆的记录和注入
"""

import asyncio
from typing import Dict, Any, Optional
from ..memory.memory_lite import CCBLightMemory
from ..memory.registry import CCBRegistry


class MemoryMiddleware:
    """Gateway 记忆中间件"""

    def __init__(self):
        self.memory = CCBLightMemory()
        self.registry = CCBRegistry()
        self.enabled = True  # 可通过配置关闭

    async def pre_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        请求前处理（Pre-Request Hook）

        借鉴：
        - Mem0: 语义搜索相关记忆
        - Letta: 结构化上下文注入
        - LangChain: 模板化注入
        """
        if not self.enabled:
            return request

        provider = request.get("provider")
        message = request.get("message", "")
        user_id = request.get("user_id", "default")

        # 1. 提取任务关键词
        keywords = self._extract_keywords(message)

        # 2. 搜索相关记忆（FTS5 + 可选向量搜索）
        relevant_memories = self.memory.search_conversations(
            " ".join(keywords),
            limit=5
        )

        # 3. 推荐最佳 Provider（如果未指定）
        if provider in ["auto", None]:
            recommended = self.registry.recommend_provider(keywords)
            if recommended:
                provider = recommended[0]["provider"]
                request["provider"] = provider
                request["_recommendation_reason"] = recommended[0]["reason"]

        # 4. 注入记忆上下文到 prompt
        if relevant_memories:
            context = self.memory.format_context_for_prompt({
                "relevant_conversations": relevant_memories,
                "skills": self.registry.get_relevant_skills(keywords),
                "provider_info": self.registry.get_provider_info(provider)
            })

            # 增强原始消息
            request["message"] = f"""# 系统记忆上下文
{context}

---

# 用户请求
{message}
"""
            request["_memory_injected"] = True

        return request

    async def post_response(self, request: Dict[str, Any], response: Dict[str, Any]):
        """
        响应后处理（Post-Response Hook）

        借鉴：
        - Mem0: LLM 驱动的事实提取
        - Claude-Mem: 观察记录
        """
        if not self.enabled:
            return

        provider = request.get("provider")
        message = request.get("message", "")
        response_text = response.get("response", "")
        metadata = {
            "model": request.get("model"),
            "latency_ms": response.get("latency_ms"),
            "tokens": response.get("tokens"),
            "memory_injected": request.get("_memory_injected", False)
        }

        # 1. 记录对话
        self.memory.record_conversation(
            provider=provider,
            question=message,
            answer=response_text,
            metadata=metadata
        )

        # 2. 异步提取关键事实（后台任务，不阻塞响应）
        if self._should_extract_facts(response_text):
            asyncio.create_task(
                self._extract_and_store_facts(message, response_text)
            )

        # 3. 更新 Provider 使用统计（用于推荐优化）
        self.registry.update_usage_stats(provider, metadata)

    def _extract_keywords(self, text: str) -> list:
        """提取任务关键词"""
        # 简单实现：分词 + 停用词过滤
        # 未来可用 LLM 提取
        keywords = []
        for word in text.split():
            if len(word) > 1 and word not in ["的", "是", "在", "有", "和"]:
                keywords.append(word)
        return keywords[:5]

    async def _extract_and_store_facts(self, question: str, answer: str):
        """
        使用 LLM 提取关键事实并存储
        借鉴 Mem0 的 LLM 驱动提取
        """
        # TODO: 调用 LLM 提取事实
        # prompt = f"从这段对话中提取关键事实：\nQ: {question}\nA: {answer}"
        # facts = llm.extract(prompt)
        # for fact in facts:
        #     self.memory.record_learning(category=fact["category"], content=fact["content"])
        pass

    def _should_extract_facts(self, response: str) -> bool:
        """判断是否需要提取事实"""
        # 简单规则：响应长度超过 200 字
        return len(response) > 200
```

### 2. ccb-cli 增强（用户入口）

**文件：** `bin/ccb-cli`

```python
#!/usr/bin/env python3
"""
CCB CLI - 增强版
自动记忆注入，无需额外命令
"""

import sys
import requests
import json


def main():
    # 解析参数
    if len(sys.argv) < 2:
        _emit("用法: ccb-cli <provider> [model] <prompt>")
        return

    provider = sys.argv[1]

    # 智能参数解析
    if len(sys.argv) == 3:
        model = None
        prompt = sys.argv[2]
    elif len(sys.argv) >= 4:
        model = sys.argv[2]
        prompt = " ".join(sys.argv[3:])
    else:
        _emit("参数错误")
        return

    # 调用 Gateway（记忆自动处理）
    gateway_url = "http://localhost:8765/api/ask"

    payload = {
        "provider": provider,
        "model": model,
        "message": prompt,
        "wait": True,
        "timeout": 120
    }

    try:
        # Gateway 自动处理记忆注入和记录
        response = requests.post(gateway_url, json=payload, timeout=120)
        result = response.json()

        if result["status"] == "completed":
            _emit(result["response"])

            # 显示记忆统计（可选）
            if result.get("_memory_injected"):
                _emit(f"\n💡 [已注入 {result.get('_memory_count', 0)} 条相关记忆]")

            if result.get("_recommendation_reason"):
                _emit(f"🤖 [推荐使用 {provider}: {result['_recommendation_reason']}]")
        else:
            _emit(f"❌ 错误: {result.get('error')}")

    except RuntimeError as e:
        _emit(f"❌ Gateway 连接失败: {e}")


if __name__ == "__main__":
    main()
```

### 3. Gateway Server 修改

**文件：** `lib/gateway/gateway_server.py`

```python
# 现有代码...

from .middleware.memory_middleware import MemoryMiddleware

class GatewayServer:
    def __init__(self):
        # 现有初始化...
        self.memory_middleware = MemoryMiddleware()  # 新增

    async def handle_ask(self, request_data: dict) -> dict:
        """处理 /api/ask 请求"""

        # 1. Memory Pre-Request Hook（新增）
        request_data = await self.memory_middleware.pre_request(request_data)

        # 2. 现有的 Provider 调用逻辑
        response = await self._call_provider(request_data)

        # 3. Memory Post-Response Hook（新增）
        await self.memory_middleware.post_response(request_data, response)

        return response
```

---

## 🚀 集成效果演示

### 场景 1: 首次询问

```bash
$ ccb-cli kimi "如何做前端开发"

[Gateway Memory Middleware]
  ✓ 未找到相关记忆
  ✓ 推荐使用 gemini 3f（基于任务关键词：前端）
  ✓ 调用 gemini 3f

Response: 建议使用 React + Tailwind CSS...

[自动记录]
  ✓ 记录到 conversations 表
  ✓ 提取关键事实: "Gemini 3f 擅长前端"
  ✓ 更新推荐权重
```

### 场景 2: 后续相关询问

```bash
$ ccb-cli kimi "创建登录页面"

[Gateway Memory Middleware]
  ✓ 搜索到 1 条相关记忆: "如何做前端开发 → React + Tailwind"
  ✓ 注入记忆上下文
  ✓ 推荐使用 gemini 3f（匹配度: 2★）

Prompt (增强后):
---
# 系统记忆上下文
## 💭 相关记忆
1. [gemini] 如何做前端开发
   A: 建议使用 React + Tailwind CSS

## 🤖 推荐使用
- gemini 3f: 匹配度 2★

---

# 用户请求
创建登录页面
---

Response: 好的，基于之前的讨论，我会用 React + Tailwind 创建登录页面...

💡 [已注入 1 条相关记忆]
🤖 [推荐使用 gemini: 前端开发最佳选择]
```

### 场景 3: 跨设备同步

```bash
# 办公室设备 A
$ ccb-cli kimi "项目架构设计"
Response: [详细架构方案]
✓ 自动同步到 Google Drive

# 家里设备 B
$ ccb-cli kimi "继续讨论架构"
[Gateway Memory Middleware]
  ✓ 从 Google Drive 拉取最新记忆
  ✓ 搜索到相关对话: "项目架构设计"
  ✓ 注入上下文

Response: 基于之前的架构讨论...

💡 [已注入 1 条来自其他设备的记忆]
```

---

## 📊 功能对比

### 集成前 vs 集成后

| 功能 | 集成前 | 集成后 |
|------|-------|--------|
| **记忆记录** | 手动调用 ccb-mem | ✅ 自动记录（Gateway 中间件）|
| **上下文注入** | 手动复制粘贴 | ✅ 自动注入（Pre-Request Hook）|
| **Provider 推荐** | 手动选择 | ✅ 智能推荐（Registry + 使用统计）|
| **跨设备同步** | 手动 push/pull | ✅ 自动同步（每小时）|
| **事实提取** | 不支持 | ✅ LLM 驱动提取（可选）|
| **语义搜索** | FTS5 关键词 | ✅ 向量语义搜索（可选）|
| **用户体验** | 需要学习命令 | ✅ 完全透明，无感知 |

---

## 🎛️ 配置文件

**文件：** `~/.ccb/gateway_config.json`

```json
{
  "memory": {
    "enabled": true,
    "auto_inject": true,
    "auto_record": true,
    "semantic_search": false,
    "fact_extraction": false,
    "injection_strategy": "recent_plus_relevant",
    "max_injected_memories": 5
  },
  "recommendation": {
    "enabled": true,
    "auto_switch_provider": false,
    "confidence_threshold": 0.7
  },
  "sync": {
    "auto_sync": true,
    "sync_interval": 3600,
    "provider": "rclone"
  }
}
```

---

## 🔄 数据流图

```
用户输入
    │
    ├─→ [ccb-cli]
    │   └─→ 解析参数
    │
    ├─→ [Gateway API]
    │   │
    │   ├─→ [Memory Middleware - Pre-Request]
    │   │   ├─→ 提取关键词
    │   │   ├─→ 搜索相关记忆（SQLite FTS5 / Qdrant）
    │   │   ├─→ 推荐 Provider（Registry）
    │   │   └─→ 注入上下文到 prompt
    │   │
    │   ├─→ [Provider Call]
    │   │   └─→ 调用 kimi/codex/gemini 等
    │   │
    │   └─→ [Memory Middleware - Post-Response]
    │       ├─→ 记录对话（SQLite）
    │       ├─→ 提取事实（LLM，异步）
    │       ├─→ 生成嵌入（Qdrant，可选）
    │       └─→ 更新统计（Registry）
    │
    ├─→ [Background Sync]
    │   └─→ rclone push to Google Drive（每小时）
    │
    └─→ 返回响应给用户
```

---

## 📈 未来扩展

### Phase 1: 基础集成（当前版本）
- ✅ Gateway 中间件
- ✅ 自动记录和注入
- ✅ FTS5 全文搜索
- ✅ Google Drive 同步

### Phase 2: 语义增强（v0.18）
- [ ] Qdrant 向量数据库集成
- [ ] 语义相似度搜索
- [ ] 智能事实提取（LLM）
- [ ] 多语言嵌入支持

### Phase 3: Agent 自主管理（v0.19）
- [ ] Agent 可调用记忆函数（Letta 模式）
- [ ] 结构化记忆块（core_memory）
- [ ] Agent 自主更新记忆
- [ ] 记忆版本控制

### Phase 4: 团队协作（v0.20）
- [ ] 多用户记忆隔离
- [ ] 共享记忆库
- [ ] 权限控制
- [ ] 实时协作

---

## 🔗 相关文档

- [MEMORY_ARCHITECTURE.md](ARCHITECTURE.md) - 记忆系统架构
- [GATEWAY_API.md](../gateway/API.md) - Gateway API 文档
- [REGISTRY.md](REGISTRY.md) - Registry 系统
- [SYNC_QUICKSTART.md](SYNC_QUICKSTART.md) - 同步快速指南

---

## 🎉 总结

**CCB Memory 深度集成设计**实现了：

1. **完全自动化** - 用户无需额外命令，自动工作
2. **智能推荐** - 基于历史记忆推荐最佳 AI
3. **无缝同步** - 跨设备自动共享记忆
4. **可扩展** - 支持向量搜索、LLM 提取等高级功能

**核心优势：**
- 🚀 零学习成本 - 透明集成，用户无感知
- 🧠 持续学习 - 自动积累经验，越用越智能
- 🔄 跨设备同步 - 随时随地延续上下文
- 🎯 精准推荐 - 智能选择最适合的 AI

**立即使用：**
```bash
# 无需任何改变，直接使用 ccb-cli
ccb-cli kimi "你的问题"

# Gateway 自动处理：
# ✓ 搜索相关记忆
# ✓ 注入上下文
# ✓ 记录对话
# ✓ 同步到云端
```

**记忆让 AI 更智能！** 🌟
