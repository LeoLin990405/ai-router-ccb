"""
CCB Gateway Memory Middleware
在 Gateway 层自动处理记忆的记录和注入
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import sys

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.memory.memory_v2 import CCBLightMemory
from lib.memory.registry import CCBRegistry
from lib.skills.skills_discovery import SkillsDiscoveryService
from .system_context import SystemContextBuilder


class MemoryMiddleware:
    """Gateway 记忆中间件"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.memory = CCBLightMemory()
        self.registry = CCBRegistry()

        # 加载配置
        self.config = config or self._load_config()
        self.enabled = self.config.get("memory", {}).get("enabled", True)
        self.auto_inject = self.config.get("memory", {}).get("auto_inject", True)
        self.auto_record = self.config.get("memory", {}).get("auto_record", True)
        self.max_injected = self.config.get("memory", {}).get("max_injected_memories", 5)
        self.inject_system_context = self.config.get("memory", {}).get("inject_system_context", True)

        # 预加载系统上下文（Skills、MCP、Providers）
        self.system_context = SystemContextBuilder()

        # 🆕 初始化 Skills Discovery Service
        self.skills_discovery = SkillsDiscoveryService()
        self.enable_skill_discovery = self.config.get("skills", {}).get("auto_discover", True)

        print(f"[MemoryMiddleware] Initialized (enabled={self.enabled})")
        print(f"[MemoryMiddleware] System context preloaded: {self.system_context.get_stats()}")
        print(f"[MemoryMiddleware] Skills discovery: {self.enable_skill_discovery}")

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        config_file = Path.home() / ".ccb" / "gateway_config.json"

        if config_file.exists():
            with open(config_file) as f:
                return json.load(f)

        # 默认配置
        return {
            "memory": {
                "enabled": True,
                "auto_inject": True,
                "auto_record": True,
                "max_injected_memories": 5,
                "inject_system_context": True,  # 新增：注入系统上下文
                "injection_strategy": "recent_plus_relevant"
            },
            "skills": {
                "auto_discover": True,  # 🆕 自动发现相关技能
                "recommend_skills": True,  # 🆕 推荐技能给用户
                "max_recommendations": 3  # 🆕 最多推荐技能数
            },
            "recommendation": {
                "enabled": True,
                "auto_switch_provider": False,
                "confidence_threshold": 0.7
            }
        }

    async def pre_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        请求前处理（Pre-Request Hook）

        功能：
        1. 提取任务关键词
        2. 搜索相关记忆
        3. 推荐最佳 Provider
        4. 注入上下文到 prompt
        """
        if not self.enabled or not self.auto_inject:
            return request

        provider = request.get("provider")
        message = request.get("message", "")
        user_id = request.get("user_id", "default")

        print(f"[MemoryMiddleware] Pre-request: provider={provider}, message_len={len(message)}")

        # 1. 提取任务关键词
        keywords = self._extract_keywords(message)
        print(f"[MemoryMiddleware] Extracted keywords: {keywords}")

        # 🆕 1.5. Skills Discovery - 发现相关技能
        skill_recommendations = None
        if self.enable_skill_discovery:
            try:
                skill_recommendations = self.skills_discovery.get_recommendations(message)
                if skill_recommendations['found']:
                    print(f"[MemoryMiddleware] {skill_recommendations['message']}")
            except Exception as e:
                print(f"[MemoryMiddleware] Skills discovery error: {e}")

        # 2. 搜索相关记忆
        relevant_memories = []
        if keywords:
            try:
                relevant_memories = self.memory.search_conversations(
                    " ".join(keywords),
                    limit=self.max_injected
                )
                print(f"[MemoryMiddleware] Found {len(relevant_memories)} relevant memories")
            except Exception as e:
                print(f"[MemoryMiddleware] Search error: {e}")

        # 3. 推荐最佳 Provider（如果启用）
        recommendation_config = self.config.get("recommendation", {})
        if recommendation_config.get("enabled", True) and provider in ["auto", None]:
            try:
                recommendations = self.registry.recommend_provider(keywords)
                if recommendations:
                    recommended_provider = recommendations[0]["provider"]
                    reason = recommendations[0]["reason"]

                    print(f"[MemoryMiddleware] Recommended: {recommended_provider} ({reason})")

                    if recommendation_config.get("auto_switch_provider", False):
                        request["provider"] = recommended_provider
                        request["_recommendation"] = {
                            "provider": recommended_provider,
                            "reason": reason,
                            "auto_switched": True
                        }
            except Exception as e:
                print(f"[MemoryMiddleware] Recommendation error: {e}")

        # 4. 注入上下文（包括系统上下文和相关记忆）
        try:
            context_parts = []

            # 4a. 注入预埋的系统上下文（Skills、MCP、Providers）
            if self.inject_system_context:
                system_ctx = self.system_context.get_relevant_context(
                    keywords,
                    provider or request.get("provider", "unknown")
                )
                if system_ctx:
                    context_parts.append(system_ctx)
                    print(f"[MemoryMiddleware] System context injected")

            # 4b. 注入相关记忆
            if relevant_memories:
                memory_ctx = self._format_memory_context(relevant_memories)
                if memory_ctx:
                    context_parts.append(memory_ctx)
                    print(f"[MemoryMiddleware] {len(relevant_memories)} memories injected")

            # 🆕 4c. 注入技能推荐（如果找到）
            if skill_recommendations and skill_recommendations['found']:
                skills_ctx = self._format_skills_context(skill_recommendations)
                if skills_ctx:
                    context_parts.append(skills_ctx)
                    print(f"[MemoryMiddleware] Skills recommendations injected")

            # 合并上下文
            if context_parts:
                full_context = "\n\n".join(context_parts)

                # 增强原始消息
                request["message"] = f"""# 系统上下文

{full_context}

---

# 用户请求
{message}
"""
                request["_memory_injected"] = True
                request["_memory_count"] = len(relevant_memories)
                request["_system_context_injected"] = self.inject_system_context
                request["_skills_recommended"] = bool(skill_recommendations and skill_recommendations['found'])

                # 🆕 Phase 1: 追踪注入详情（如果有 request_id）
                request_id = request.get("request_id")
                if request_id:
                    self._track_injection(
                        request_id=request_id,
                        provider=provider,
                        original_message=message,
                        memories=relevant_memories,
                        skills=skill_recommendations,
                        system_context_injected=self.inject_system_context
                    )

        except Exception as e:
            print(f"[MemoryMiddleware] Context injection error: {e}")

        return request

    async def post_response(self, request: Dict[str, Any], response: Dict[str, Any]):
        """
        响应后处理（Post-Response Hook）

        功能：
        1. 记录对话
        2. 更新统计
        3. （可选）提取关键事实
        """
        if not self.enabled or not self.auto_record:
            return

        try:
            provider = request.get("provider", "unknown")
            message = request.get("message", "")

            # 移除注入的上下文，只保存原始问题
            if request.get("_memory_injected"):
                # 提取原始问题（在 "# 用户请求" 之后）
                parts = message.split("# 用户请求")
                if len(parts) > 1:
                    message = parts[1].strip()

            response_text = response.get("response", "")

            metadata = {
                "model": request.get("model"),
                "latency_ms": response.get("latency_ms"),
                "tokens": response.get("tokens"),
                "memory_injected": request.get("_memory_injected", False),
                "memory_count": request.get("_memory_count", 0)
            }

            # 记录对话
            self.memory.record_conversation(
                provider=provider,
                question=message,
                answer=response_text,
                metadata=metadata
            )

            print(f"[MemoryMiddleware] Conversation recorded: provider={provider}")

            # 🆕 记录技能使用（如果响应中提到了技能）
            if self.enable_skill_discovery:
                self._record_skill_usage(request, response)

            # 更新统计（用于推荐优化）
            # self.registry.update_usage_stats(provider, metadata)

        except Exception as e:
            print(f"[MemoryMiddleware] Post-response error: {e}")

    def _extract_keywords(self, text: str) -> List[str]:
        """提取任务关键词（简单实现）"""
        # 中文停用词
        stop_words = {
            "的", "是", "在", "有", "和", "了", "我", "你", "他", "她",
            "这", "那", "一个", "怎么", "如何", "什么", "为什么",
            "help", "me", "with", "can", "you", "please", "the", "a", "an"
        }

        # 分词（简单空格分割）
        words = text.lower().split()

        # 过滤停用词和短词
        keywords = [
            w for w in words
            if len(w) > 1 and w not in stop_words
        ]

        return keywords[:10]  # 最多保留 10 个关键词

    def _format_memory_context(self, memories: List[Dict[str, Any]]) -> str:
        """格式化记忆上下文（只包含对话记忆）"""
        if not memories:
            return ""

        context_parts = ["## 💭 相关记忆"]

        for i, mem in enumerate(memories, 1):
            provider_name = mem.get("provider", "unknown")
            question = mem.get("question", "")[:100]
            answer = mem.get("answer", "")[:200]
            context_parts.append(f"{i}. [{provider_name}] {question}")
            context_parts.append(f"   A: {answer}...")
            context_parts.append("")

        return "\n".join(context_parts)

    def _format_skills_context(self, recommendations: Dict[str, Any]) -> str:
        """格式化技能推荐上下文（🆕 新增）"""
        if not recommendations or not recommendations.get('found'):
            return ""

        context_parts = ["## 🛠️ 相关技能推荐"]

        for skill in recommendations.get('skills', []):
            name = skill['name']
            description = skill['description']
            installed = skill['installed']
            relevance = skill['relevance_score']

            if installed:
                # 已安装的技能
                context_parts.append(
                    f"- **/{name}** (score: {relevance}) - {description}"
                )
                context_parts.append(f"  ✓ 已安装，可直接使用: `/{name}`")
            else:
                # 未安装的技能
                context_parts.append(
                    f"- **{name}** (score: {relevance}) - {description}"
                )
                context_parts.append(f"  ⚠️ 未安装，建议安装后使用")

        return "\n".join(context_parts)

    def _format_context(
        self,
        memories: List[Dict[str, Any]],
        keywords: List[str],
        provider: str
    ) -> str:
        """格式化记忆上下文（已弃用，保留兼容性）"""
        return self._format_memory_context(memories)

    def get_stats(self) -> Dict[str, Any]:
        """获取中间件统计信息"""
        return {
            "enabled": self.enabled,
            "auto_inject": self.auto_inject,
            "auto_record": self.auto_record,
            "memory_stats": self.memory.get_stats()
        }

    def _record_skill_usage(self, request: Dict[str, Any], response: Dict[str, Any]):
        """记录技能使用情况（🆕 新增）"""
        try:
            response_text = response.get("response", "")
            message = request.get("message", "")
            provider = request.get("provider", "unknown")

            # 检测响应中是否提到了技能（通过 /skill-name 模式）
            import re
            skill_mentions = re.findall(r'/([a-z0-9\-]+)', response_text)

            if skill_mentions:
                keywords = " ".join(self._extract_keywords(message))

                for skill_name in skill_mentions:
                    # 记录使用
                    self.skills_discovery.record_usage(
                        skill_name=skill_name,
                        task_keywords=keywords,
                        provider=provider,
                        success=True
                    )

                print(f"[MemoryMiddleware] Recorded skill usage: {skill_mentions}")

        except Exception as e:
            print(f"[MemoryMiddleware] Skill usage recording error: {e}")

    def _track_injection(
        self,
        request_id: str,
        provider: str,
        original_message: str,
        memories: List[Dict[str, Any]],
        skills: Optional[Dict[str, Any]],
        system_context_injected: bool
    ):
        """追踪记忆注入详情（Phase 1: Transparency）"""
        try:
            # 提取记忆 IDs 和相关性分数
            memory_ids = []
            relevance_scores = {}
            for mem in memories:
                mem_id = mem.get("id") or mem.get("message_id")
                if mem_id:
                    memory_ids.append(mem_id)
                    # 如果有相关性分数
                    if mem.get("relevance_score"):
                        relevance_scores[mem_id] = mem.get("relevance_score")

            # 提取技能名称
            skill_names = []
            if skills and skills.get("found"):
                for skill in skills.get("skills", []):
                    skill_names.append(skill.get("name"))

            # 使用 memory v2 追踪
            self.memory.v2.track_request_injection(
                request_id=request_id,
                provider=provider,
                original_message=original_message,
                injected_memory_ids=memory_ids,
                injected_skills=skill_names,
                injected_system_context=system_context_injected,
                relevance_scores=relevance_scores,
                metadata={
                    "memory_count": len(memories),
                    "skills_count": len(skill_names),
                    "system_context": system_context_injected
                }
            )

            print(f"[MemoryMiddleware] Tracked injection for {request_id}: "
                  f"{len(memory_ids)} memories, {len(skill_names)} skills")

        except Exception as e:
            print(f"[MemoryMiddleware] Injection tracking error: {e}")

    # ========================================================================
    # Discussion Memory (Phase 6)
    # ========================================================================

    async def post_discussion(
        self,
        session_id: str,
        topic: str,
        providers: List[str],
        summary: str = None,
        insights: List[Dict[str, Any]] = None,
        messages: List[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Record a discussion to memory system (Phase 6)

        Args:
            session_id: Discussion session ID
            topic: Discussion topic
            providers: List of participating providers
            summary: Discussion summary
            insights: Extracted insights
            messages: Discussion messages

        Returns:
            observation_id if recorded, None otherwise
        """
        if not self.enabled or not self.auto_record:
            return None

        try:
            observation_id = self.memory.v2.record_discussion(
                session_id=session_id,
                topic=topic,
                providers=providers,
                summary=summary,
                insights=insights,
                messages=messages
            )

            print(f"[MemoryMiddleware] Discussion recorded: {session_id} -> {observation_id}")
            return observation_id

        except Exception as e:
            print(f"[MemoryMiddleware] Discussion recording error: {e}")
            return None
