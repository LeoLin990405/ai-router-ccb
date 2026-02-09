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


class MemoryMiddlewareCoreMixin:
    """Mixin methods extracted from MemoryMiddleware."""

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

        # v1.1 shared knowledge hook (injected by GatewayServer)
        self._shared_knowledge = None

        # 🆕 v2.0: 启发式检索器
        self.heuristic_retriever = None
        self.use_heuristic = self.config.get("memory", {}).get("use_heuristic_retrieval", True)
        if HAS_HEURISTIC and self.use_heuristic:
            try:
                self.heuristic_retriever = HeuristicRetriever()
                logger.info(f"Heuristic retriever initialized")
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                logger.info(f"Heuristic retriever init error: {e}")

        logger.info(f"Initialized (enabled={self.enabled}, heuristic={self.heuristic_retriever is not None})")
        logger.info(f"System context preloaded: {self.system_context.get_stats()}")
        logger.info(f"Skills discovery: {self.enable_skill_discovery}")

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
                "injection_strategy": "recent_plus_relevant",
                "use_heuristic_retrieval": True  # v2.0: 使用启发式检索
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

        logger.info(f"Pre-request: provider={provider}, message_len={len(message)}")

        # 1. 提取任务关键词
        keywords = self._extract_keywords(message)
        logger.info(f"Extracted keywords: {keywords}")

        # 🆕 1.5. Skills Discovery - 发现相关技能
        skill_recommendations = None
        if self.enable_skill_discovery:
            try:
                skill_recommendations = self.skills_discovery.get_recommendations(message)
                if skill_recommendations['found']:
                    logger.info(f"{skill_recommendations['message']}")
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                logger.info(f"Skills discovery error: {e}")

        # 2. 搜索相关记忆 (v2.0: 使用启发式检索)
        relevant_memories = []
        heuristic_results = []  # v2.0: 保存评分结果
        if keywords:
            try:
                if self.heuristic_retriever:
                    # v2.0: 使用 HeuristicRetriever 的 αR + βI + γT 评分
                    heuristic_results = self.heuristic_retriever.retrieve(
                        " ".join(keywords),
                        limit=self.max_injected,
                        request_id=request.get("request_id"),
                        track_access=True
                    )
                    # 转换为兼容格式
                    relevant_memories = [
                        {
                            "id": m.memory_id,
                            "message_id": m.memory_id,
                            "provider": m.provider,
                            "question": "",
                            "answer": m.content[:300] if m.role == 'assistant' else m.content[:300],
                            "timestamp": m.timestamp,
                            "relevance_score": m.relevance_score,
                            "importance_score": m.importance_score,
                            "recency_score": m.recency_score,
                            "final_score": m.final_score
                        }
                        for m in heuristic_results
                    ]
                    logger.info(f"Heuristic search: found {len(relevant_memories)} memories")
                else:
                    # 回退到基本搜索
                    relevant_memories = self.memory.search_conversations(
                        " ".join(keywords),
                        limit=self.max_injected
                    )
                    logger.info(f"Basic search: found {len(relevant_memories)} memories")
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                logger.info(f"Search error: {e}")

        # 3. 推荐最佳 Provider（如果启用）
        logger.info(f"Provider before recommendation: {provider}")
        recommendation_config = self.config.get("recommendation", {})
        if recommendation_config.get("enabled", True) and provider in ["auto", None]:
            logger.info(f"Entering recommendation logic (provider={provider})")
            try:
                recommendations = self.registry.recommend_provider(keywords)
                if recommendations:
                    recommended_provider = recommendations[0]["provider"]
                    reason = recommendations[0]["reason"]

                    logger.info(f"Recommended: {recommended_provider} ({reason})")

                    if recommendation_config.get("auto_switch_provider", False):
                        logger.info(f"Auto-switching provider: {provider} -> {recommended_provider}")
                        request["provider"] = recommended_provider
                        request["_recommendation"] = {
                            "provider": recommended_provider,
                            "reason": reason,
                            "auto_switched": True
                        }
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                logger.info(f"Recommendation error: {e}")

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
                    logger.info(f"System context injected")

            # 4b. 注入相关记忆
            if relevant_memories:
                memory_ctx = self._format_memory_context(relevant_memories)
                if memory_ctx:
                    context_parts.append(memory_ctx)
                    logger.info(f"{len(relevant_memories)} memories injected")

            # 🆕 4c. 注入技能推荐（如果找到）
            if skill_recommendations and skill_recommendations['found']:
                skills_ctx = self._format_skills_context(skill_recommendations)
                if skills_ctx:
                    context_parts.append(skills_ctx)
                    logger.info(f"Skills recommendations injected")

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

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.info(f"Context injection error: {e}")

        return request

    def _extract_keywords(self, text: str) -> List[str]:
        """提取任务关键词（v3: 使用本地 LLM 提取语义关键词）"""
        # 尝试使用 LLM 提取，如果失败则回退到正则提取
        try:
            return self._extract_keywords_with_llm(text)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.info(f"LLM extraction failed: {e}, fallback to regex")
            return self._extract_keywords_regex(text)

    def _extract_keywords_with_llm(self, text: str) -> List[str]:
        """
        使用 Ollama 智能路由提取关键词

        路由策略：
        1. 首选本地 qwen2.5:7b（快速，无网络依赖）
        2. 本地超时/失败 → 自动切换云端 deepseek-v3.1:671b-cloud
        3. 云端失败 → 回退到正则提取
        """
        import requests
        import re

        # 清理文本
        cleaned = re.sub(r'\s+', ' ', text).strip()

        # 短查询直接返回
        if len(cleaned) <= 10:
            return [cleaned]

        # 构造提示词
        prompt = f"""从下面的问题中提取2-3个最核心的关键词（名词或名词短语），用逗号分隔。
只返回关键词，不要其他解释。

问题：{cleaned}

关键词："""

        # 模型路由配置
        models = [
            {
                'name': 'qwen2.5:7b',
                'timeout': 6,      # 本地模型 6 秒超时（冷启动 ~5s，热调用 <1s）
                'location': 'local'
            },
            {
                'name': 'deepseek-v3.1:671b-cloud',
                'timeout': 10,     # 云端模型 10 秒超时
                'location': 'cloud'
            }
        ]

        last_error = None
        for model_config in models:
            model_name = model_config['name']
            timeout = model_config['timeout']
            location = model_config['location']

            try:
                response = requests.post(
                    'http://localhost:11434/api/generate',
                    json={
                        'model': model_name,
                        'prompt': prompt,
                        'stream': False,
                        'options': {
                            'temperature': 0.3,
                            'num_predict': 50
                        }
                    },
                    timeout=timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    keywords_str = result.get('response', '').strip()

                    # 解析关键词
                    keywords = []
                    raw_keywords = re.split(r'[,，、]', keywords_str)

                    for kw in raw_keywords:
                        cleaned_kw = re.sub(r'^[\d\.\s、]+', '', kw.strip())
                        cleaned_kw = re.sub(r'[。！？,.!?、]+$', '', cleaned_kw)
                        if cleaned_kw and len(cleaned_kw) >= 2:
                            keywords.append(cleaned_kw)

                    if keywords:
                        logger.info(f"LLM extracted ({location}:{model_name}): {keywords}")
                        return keywords[:5]

            except requests.exceptions.Timeout:
                logger.info(f"Ollama timeout ({timeout}s) for {location}:{model_name}")
                last_error = f"timeout:{model_name}"
                continue  # 尝试下一个模型
            except requests.exceptions.ConnectionError:
                logger.info(f"Ollama not running on localhost:11434")
                last_error = "connection_error"
                break  # Ollama 服务未运行，直接退出
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                logger.info(f"Ollama API error ({model_name}): {e}")
                last_error = str(e)
                continue  # 尝试下一个模型

        # 所有模型都失败
        raise Exception(f"LLM extraction failed, fallback to regex")

    def _extract_keywords_regex(self, text: str) -> List[str]:
        """正则提取关键词（回退方案）"""
        import re

        # 清理：移除多余空格和换行
        cleaned = re.sub(r'\s+', ' ', text).strip()

        # 中文停用词（疑问词和助词）
        stop_words = {
            "的", "是", "在", "有", "和", "了", "我", "你", "他", "她",
            "这", "那", "一个", "怎么", "如何", "什么", "为什么", "需要",
            "可以", "还", "刚才", "提到", "考虑", "吗", "呢", "吧", "要",
            "会", "能", "将", "被", "把", "对", "给", "让", "向", "从",
            "注意", "关注", "思考", "想要", "知道", "了解", "哪些",
        }

        # 提取 3-4 字的中文名词（通常是实体词）
        # 如："购物车"、"电商网站"、"React组件"
        chinese_keywords = re.findall(r'[\u4e00-\u9fff]{3,4}', cleaned)

        # 提取英文单词（3字母以上）
        english_keywords = re.findall(r'\b[a-zA-Z]{3,}\b', cleaned.lower())

        # 过滤停用词
        keywords = []
        for word in chinese_keywords + english_keywords:
            if word not in stop_words and len(word) >= 2:
                keywords.append(word)

        # 去重
        seen = set()
        unique_keywords = []
        for k in keywords:
            if k not in seen:
                seen.add(k)
                unique_keywords.append(k)

        # 如果提取到关键词，返回前5个最重要的
        # 如果没有关键词，返回清理后的原文（短查询）
        if unique_keywords:
            return unique_keywords[:5]
        else:
            # 对于短查询（如"购物车"），直接返回
            return [cleaned] if len(cleaned) <= 10 else []

