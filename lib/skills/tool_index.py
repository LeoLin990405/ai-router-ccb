"""Unified Tool Index for skills, MCP tools, and MCP servers."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from lib.common.logging import get_logger
except ImportError:  # pragma: no cover - script mode fallback
    from common.logging import get_logger  # type: ignore

logger = get_logger("skills.tool_index")

INDEX_PATH = Path.home() / ".ccb_config" / "tool_index.json"

ZH_EN_KEYWORDS = {
    "前端": ["frontend", "react", "vue", "css", "html", "ui"],
    "后端": ["backend", "server", "api", "database"],
    "数据库": ["database", "sql", "postgres", "mysql", "sqlite"],
    "测试": ["test", "testing", "unittest", "pytest"],
    "部署": ["deploy", "deployment", "docker", "ci", "cd"],
    "文档": ["doc", "documentation", "readme", "markdown"],
    "图表": ["chart", "graph", "visualization", "plot"],
    "安全": ["security", "auth", "encryption"],
    "爬虫": ["crawler", "scraper", "spider", "web scraping"],
    "机器学习": ["ml", "machine learning", "ai", "model"],
    "数据分析": ["data analysis", "analytics", "statistics"],
    "自动化": ["automation", "workflow", "pipeline"],
    "版本控制": ["git", "version control", "svn"],
    "演示": ["presentation", "slides", "pptx"],
    "表格": ["spreadsheet", "excel", "xlsx", "csv"],
    "pdf": ["pdf", "document"],
    "笔记": ["notes", "notebook", "obsidian"],
}


class ToolIndex:
    """Unified index for discovering tools across all sources."""

    def __init__(self, index_path: Optional[str | Path] = None):
        self._path = Path(index_path) if index_path else INDEX_PATH
        self._entries: List[Dict[str, Any]] = []
        self._built_at: Optional[str] = None
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            logger.debug("No tool index found at %s", self._path)
            return

        try:
            raw_text = self._path.read_text(encoding="utf-8")
            if not raw_text.strip():
                return
            payload = json.loads(raw_text)
            entries = payload.get("entries", []) if isinstance(payload, dict) else []
            if isinstance(entries, list):
                self._entries = [entry for entry in entries if isinstance(entry, dict)]
            self._built_at = payload.get("built_at") if isinstance(payload, dict) else None
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            logger.warning("Failed to load tool index at %s", self._path, exc_info=True)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._built_at = now
        payload = {
            "version": "1.1.0",
            "built_at": now,
            "entries": self._entries,
        }
        self._path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @property
    def stats(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        installed = 0
        for entry in self._entries:
            type_name = str(entry.get("type") or "unknown")
            by_type[type_name] = by_type.get(type_name, 0) + 1
            if bool(entry.get("installed")):
                installed += 1

        return {
            "total": len(self._entries),
            "installed": installed,
            "by_type": by_type,
            "built_at": self._built_at,
        }

    def set_entries(self, entries: List[Dict[str, Any]]) -> None:
        self._entries = [entry for entry in entries if isinstance(entry, dict)]
        self.save()

    def add_entry(self, entry: Dict[str, Any]) -> None:
        entry_id = entry.get("id")
        if not entry_id:
            return
        self._entries = [existing for existing in self._entries if existing.get("id") != entry_id]
        self._entries.append(entry)

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        for entry in self._entries:
            if entry.get("id") == entry_id:
                return entry
        return None

    def list_entries(self) -> List[Dict[str, Any]]:
        return list(self._entries)

    def search(
        self,
        query: str,
        limit: int = 10,
        installed_only: bool = False,
        types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        query_lower = str(query or "").strip().lower()
        if not query_lower:
            return []

        query_words = {word for word in re.split(r"[\s,;/]+", query_lower) if word}
        expanded_words = set(query_words)

        for zh_word, en_words in ZH_EN_KEYWORDS.items():
            if zh_word in query_lower:
                expanded_words.update(en_words)

        allowed_types = {item.strip() for item in types} if types else None
        results: List[Dict[str, Any]] = []

        for entry in self._entries:
            if installed_only and not bool(entry.get("installed")):
                continue
            if allowed_types and str(entry.get("type")) not in allowed_types:
                continue

            score = self._score_entry(
                entry=entry,
                query_lower=query_lower,
                query_words=query_words,
                expanded_words=expanded_words,
            )
            if score > 0:
                results.append({**entry, "_score": round(score, 4)})

        results.sort(key=lambda item: float(item.get("_score", 0.0)), reverse=True)
        return results[:limit]

    def _score_entry(
        self,
        *,
        entry: Dict[str, Any],
        query_lower: str,
        query_words: set[str],
        expanded_words: set[str],
    ) -> float:
        score = 0.0

        name = str(entry.get("name") or "").lower()
        description = str(entry.get("description") or "").lower()
        keywords = [str(item).lower() for item in entry.get("keywords", []) if item]
        triggers = [str(item).lower() for item in entry.get("triggers", []) if item]

        for trigger in triggers:
            if trigger and (trigger in query_lower or query_lower in trigger):
                score += 3.0
                break

        keyword_matches = 0
        for keyword in keywords:
            if keyword in expanded_words:
                keyword_matches += 1
            elif keyword and keyword in query_lower:
                keyword_matches += 1
            elif any(word in keyword for word in expanded_words if len(word) >= 2):
                keyword_matches += 1
        score += min(keyword_matches * 2.0, 6.0)

        if name and (name in query_lower or any(word in name for word in query_words)):
            score += 2.0

        description_words = {word for word in re.split(r"[\s,;/]+", description) if word}
        desc_matches = len(expanded_words & description_words)
        score += min(desc_matches * 1.0, 3.0)

        if bool(entry.get("installed")):
            score += 0.5

        usage_count = entry.get("usage_count")
        try:
            usage_value = float(usage_count)
        except (TypeError, ValueError):
            usage_value = 0.0
        if usage_value > 0:
            score += min(usage_value / 100.0, 0.5)

        return score
