"""Auto-split mixins for gateway MemoryMiddleware."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.common.logging import get_logger
from lib.memory.memory_v2 import CCBLightMemory
from lib.memory.registry import CCBRegistry
from lib.skills.skills_discovery import SkillsDiscoveryService

from .system_context import SystemContextBuilder

try:
    from lib.memory.heuristic_retriever import HeuristicRetriever, ScoredMemory
    HAS_HEURISTIC = True
except ImportError:
    HAS_HEURISTIC = False


logger = get_logger("gateway.middleware.memory")


class MemoryMiddlewarePostMixin:
    """Mixin methods extracted from MemoryMiddleware."""

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

            logger.info(f"Conversation recorded: provider={provider}")

            # 🆕 记录技能使用（如果响应中提到了技能）
            if self.enable_skill_discovery:
                self._record_skill_usage(request, response)

            # v1.1: 自动发布高质量响应到 Shared Knowledge
            await self._maybe_auto_publish(request, response)

            # 更新统计（用于推荐优化）
            # self.registry.update_usage_stats(provider, metadata)

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.info(f"Post-response error: {e}")

    def _format_memory_context(self, memories: List[Dict[str, Any]]) -> str:
        """格式化记忆上下文（v2.0: 包含评分信息）"""
        if not memories:
            return ""

        context_parts = ["## 💭 相关记忆"]

        for i, mem in enumerate(memories, 1):
            provider_name = mem.get("provider", "unknown")
            question = mem.get("question", "")[:100]
            answer = mem.get("answer", "")[:200]

            # v2.0: 如果有评分，显示评分信息
            score_info = ""
            if mem.get("final_score") is not None:
                score_info = f" (score: {mem['final_score']:.2f})"

            context_parts.append(f"{i}. [{provider_name}]{score_info} {question}")
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
        """获取中间件统计信息 (v2.0: 包含启发式检索统计)"""
        stats = {
            "enabled": self.enabled,
            "auto_inject": self.auto_inject,
            "auto_record": self.auto_record,
            "memory_stats": self.memory.get_stats(),
            "heuristic_enabled": self.heuristic_retriever is not None
        }

        # v2.0: 添加启发式检索统计
        if self.heuristic_retriever:
            try:
                stats["heuristic_stats"] = self.heuristic_retriever.get_statistics()
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                stats["heuristic_error"] = str(e)

        return stats

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

                logger.info(f"Recorded skill usage: {skill_mentions}")

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.info(f"Skill usage recording error: {e}")

    async def _maybe_auto_publish(self, request_data: Dict[str, Any], response_data: Dict[str, Any]) -> None:
        """Auto-publish high-quality responses to shared knowledge."""
        shared_service = getattr(self, "_shared_knowledge", None)
        if shared_service is None:
            return

        response_text = str(response_data.get("response", "") or "").strip()
        if not response_text or len(response_text) < 200:
            return

        has_code = "```" in response_text
        has_structure = response_text.count("\n") > 10
        if not (has_code or has_structure):
            return

        provider = str(request_data.get("provider", "unknown") or "unknown")
        message = str(request_data.get("message", "") or "")
        title = message[:120] if message else f"Auto insight from {provider}"

        category = "solution" if has_code else "learning"
        tags = self._extract_tags(message)

        metadata = {
            "auto_published": True,
            "provider": provider,
            "model": request_data.get("model"),
            "latency_ms": response_data.get("latency_ms"),
            "tokens": response_data.get("tokens"),
        }

        try:
            shared_service.publish(
                agent_id=f"{provider}-auto",
                category=category,
                title=title,
                content=response_text[:2000],
                tags=tags,
                source_request_id=request_data.get("request_id"),
                metadata=metadata,
            )
            logger.debug("Auto-published shared knowledge from provider %s", provider)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            logger.debug("Auto-publish failed", exc_info=True)

    def _extract_tags(self, text: str) -> List[str]:
        """Extract compact keyword tags from text."""
        import re

        words = re.findall(r"\b[a-zA-Z]{3,15}\b", text.lower())
        stopwords = {
            "the",
            "and",
            "for",
            "this",
            "that",
            "with",
            "from",
            "have",
            "are",
            "was",
            "your",
            "into",
            "about",
            "when",
            "then",
        }

        tags: List[str] = []
        for word in words:
            if word in stopwords:
                continue
            if word not in tags:
                tags.append(word)
            if len(tags) >= 5:
                break

        return tags

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

            logger.info(f"Tracked injection for {request_id}: "
                  f"{len(memory_ids)} memories, {len(skill_names)} skills")

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.info(f"Injection tracking error: {e}")

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

            logger.info(f"Discussion recorded: {session_id} -> {observation_id}")
            return observation_id

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.info(f"Discussion recording error: {e}")
            return None

