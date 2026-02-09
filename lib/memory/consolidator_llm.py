"""Auto-split mixin methods for NightlyConsolidator."""
from __future__ import annotations

import asyncio
import json
import math
import re
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .consolidator_models import SessionArchive
from .consolidator_shared import CONSOLIDATOR_ERRORS, HAS_HTTPX, httpx, logger


class ConsolidatorLLMMixin:
    """Mixin methods extracted from NightlyConsolidator."""

    async def consolidate_with_llm(self, hours: int = 24) -> Dict[str, Any]:
        """
        LLM-enhanced consolidation (Phase 3: LLM Consolidator).

        Uses LLM to extract deeper insights from sessions.

        Args:
            hours: How many hours back to look for sessions

        Returns:
            Consolidated memory dictionary with LLM insights
        """
        # First do basic consolidation
        memory = self.consolidate(hours=hours)

        if memory.get("status") == "no_sessions":
            return memory

        # If no httpx or gateway unavailable, return basic consolidation
        if not HAS_HTTPX:
            memory["llm_enhanced"] = False
            memory["llm_error"] = "httpx not installed"
            return memory

        # Collect raw session data for LLM analysis
        cutoff = datetime.now() - timedelta(hours=hours)
        archives = self._collect_archives(cutoff)
        sessions = [SessionArchive(path) for path in archives]

        # Extract insights via LLM
        try:
            llm_insights = await self._extract_insights_via_llm(sessions, memory)

            if llm_insights:
                memory["llm_enhanced"] = True
                memory["llm_learnings"] = llm_insights.get("learnings", [])
                memory["llm_preferences"] = llm_insights.get("preferences", [])
                memory["llm_patterns"] = llm_insights.get("patterns", [])
                memory["llm_summary"] = llm_insights.get("summary", "")

                # Save updated memory
                self._save_memory(memory)
            else:
                memory["llm_enhanced"] = False
                memory["llm_error"] = "No insights extracted"

        except CONSOLIDATOR_ERRORS as e:
            memory["llm_enhanced"] = False
            memory["llm_error"] = str(e)

        return memory

    async def _extract_insights_via_llm(
        self,
        sessions: List['SessionArchive'],
        basic_memory: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Call LLM to extract deeper insights from sessions.

        Args:
            sessions: Parsed session archives
            basic_memory: Basic consolidated memory

        Returns:
            LLM-extracted insights dict or None
        """
        # Build prompt
        prompt = self._build_consolidation_prompt(sessions, basic_memory)

        # Call Gateway API
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.GATEWAY_URL}/api/ask",
                    params={"wait": "true", "timeout": "90"},
                    json={
                        "message": prompt,
                        "provider": self.llm_provider
                    }
                )

                if response.status_code != 200:
                    logger.warning("LLM request failed: %s", response.status_code)
                    return None

                result = response.json()

                # Parse LLM response
                llm_response = result.get("response", "")
                return self._parse_llm_response(llm_response)

        except httpx.TimeoutException:
            logger.warning("LLM request timed out")
            return None
        except CONSOLIDATOR_ERRORS as e:
            logger.warning("LLM request error: %s", e)
            return None

    def _build_consolidation_prompt(
        self,
        sessions: List['SessionArchive'],
        basic_memory: Dict[str, Any]
    ) -> str:
        """
        Build prompt for LLM consolidation.

        Args:
            sessions: Parsed session archives
            basic_memory: Basic consolidated memory

        Returns:
            Formatted prompt string
        """
        # Summarize sessions
        session_summaries = []
        for s in sessions[:10]:  # Limit to 10 sessions
            summary = f"""
Session: {s.session_id[:8]}
Project: {s.project_path}
Task: {s.task_summary[:200] if s.task_summary else 'N/A'}
Tools: {', '.join(list(s.tool_calls.keys())[:5])}
Learnings: {'; '.join(s.learnings[:3])}
"""
            session_summaries.append(summary)

        # Format basic insights
        basic_insights = "\n".join([
            f"- {i['pattern']}"
            for i in basic_memory.get("cross_session_insights", [])
        ])

        # Build prompt
        prompt = f"""你是一个记忆整合分析师。请分析以下用户的最近 AI 会话记录，提取有价值的洞察。

## 会话概览
- 处理的会话数: {len(sessions)}
- 时间范围: {basic_memory.get('time_range_hours', 24)} 小时
- 使用的模型: {', '.join(basic_memory.get('models_used', []))}

## 会话详情
{''.join(session_summaries)}

## 已有的基础洞察
{basic_insights if basic_insights else '无'}

## 所有学到的知识
{chr(10).join(['- ' + l for l in basic_memory.get('all_learnings', [])[:15]])}

---

请分析以上信息，输出 JSON 格式的结构化洞察：

```json
{{
  "summary": "一句话总结用户这段时间的主要活动",
  "learnings": [
    {{"content": "具体的学习内容", "confidence": 0.9, "category": "technical"}},
    ...
  ],
  "preferences": [
    {{"type": "工作习惯/工具偏好/编码风格", "value": "具体偏好", "evidence": "证据来源"}}
  ],
  "patterns": [
    {{"pattern": "发现的行为模式", "frequency": 3, "significance": "为什么重要"}}
  ]
}}
```

注意：
1. learnings 的 category 可选: "technical", "workflow", "preference", "insight"
2. confidence 范围 0-1，表示确定程度
3. 只输出有价值的、可操作的洞察
4. 用中文回答
"""
        return prompt

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Parse LLM response to extract structured insights.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed insights dict or None
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    return None

            parsed = json.loads(json_str)

            # Validate structure
            result = {
                "summary": parsed.get("summary", ""),
                "learnings": [],
                "preferences": [],
                "patterns": []
            }

            # Parse learnings
            for learning in parsed.get("learnings", []):
                if isinstance(learning, dict) and learning.get("content"):
                    result["learnings"].append({
                        "content": learning["content"],
                        "confidence": float(learning.get("confidence", 0.8)),
                        "category": learning.get("category", "insight")
                    })

            # Parse preferences
            for pref in parsed.get("preferences", []):
                if isinstance(pref, dict) and pref.get("value"):
                    result["preferences"].append({
                        "type": pref.get("type", "unknown"),
                        "value": pref["value"],
                        "evidence": pref.get("evidence", "")
                    })

            # Parse patterns
            for pattern in parsed.get("patterns", []):
                if isinstance(pattern, dict) and pattern.get("pattern"):
                    result["patterns"].append({
                        "pattern": pattern["pattern"],
                        "frequency": int(pattern.get("frequency", 1)),
                        "significance": pattern.get("significance", "")
                    })

            return result

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM JSON: %s", e)
            return None
        except CONSOLIDATOR_ERRORS as e:
            logger.warning("LLM parse error: %s", e)
            return None

