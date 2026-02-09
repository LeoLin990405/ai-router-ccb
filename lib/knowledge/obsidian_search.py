"""Obsidian 本地笔记搜索。"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import yaml


class ObsidianSearch:
    """Obsidian Vault 搜索器。"""

    def __init__(self, vault_path: str, excluded_folders: Optional[List[str]] = None):
        self.vault_path = Path(vault_path).expanduser()
        self.excluded_folders = excluded_folders or [".obsidian", ".trash"]

        if not self.vault_path.exists():
            raise ValueError(f"Vault not found: {self.vault_path}")

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """全文搜索。"""
        results: List[Dict[str, Any]] = []
        query_lower = query.lower().strip()
        if not query_lower:
            return results

        query_words = [word for word in query_lower.split() if word]
        if not query_words:
            return results

        for md_file in self._iter_markdown_files():
            try:
                content = md_file.read_text(encoding="utf-8")
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                continue

            content_lower = content.lower()
            score = self._calculate_relevance(content_lower, query_words)
            if score <= 0:
                continue

            metadata = self._extract_metadata(content)
            title = metadata.get("title") if isinstance(metadata, dict) else None
            tags = metadata.get("tags") if isinstance(metadata, dict) else []

            if isinstance(tags, str):
                tags = [tags]
            if not isinstance(tags, list):
                tags = []

            results.append(
                {
                    "path": str(md_file.relative_to(self.vault_path)),
                    "title": title or md_file.stem,
                    "tags": tags,
                    "score": score,
                    "snippet": self._extract_snippet(content, query_words),
                    "modified_at": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat(),
                }
            )

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def search_by_tag(self, tag: str, limit: int = 20) -> List[Dict[str, Any]]:
        """按标签搜索。"""
        normalized_tag = tag.strip().lstrip("#")
        if not normalized_tag:
            return []

        pattern = re.compile(rf"(^|\s)#{re.escape(normalized_tag)}([\s.,;:!?]|$)")
        results: List[Dict[str, Any]] = []

        for md_file in self._iter_markdown_files():
            try:
                content = md_file.read_text(encoding="utf-8")
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                continue

            if not pattern.search(content):
                continue

            metadata = self._extract_metadata(content)
            title = metadata.get("title") if isinstance(metadata, dict) else None
            tags = metadata.get("tags") if isinstance(metadata, dict) else []

            if isinstance(tags, str):
                tags = [tags]
            if not isinstance(tags, list):
                tags = []

            results.append(
                {
                    "path": str(md_file.relative_to(self.vault_path)),
                    "title": title or md_file.stem,
                    "tags": tags,
                }
            )

            if len(results) >= limit:
                break

        return results

    def get_note(self, path: str) -> Optional[Dict[str, Any]]:
        """获取笔记内容。"""
        full_path = (self.vault_path / path).resolve()
        if not full_path.exists() or not full_path.is_file():
            return None

        try:
            full_path.relative_to(self.vault_path.resolve())
        except ValueError:
            return None

        try:
            content = full_path.read_text(encoding="utf-8")
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return None

        metadata = self._extract_metadata(content)
        title = metadata.get("title") if isinstance(metadata, dict) else None
        tags = metadata.get("tags") if isinstance(metadata, dict) else []

        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list):
            tags = []

        return {
            "path": path,
            "title": title or full_path.stem,
            "tags": tags,
            "content": content,
            "word_count": len(content.split()),
        }

    def _iter_markdown_files(self) -> Generator[Path, None, None]:
        """遍历所有 Markdown 文件。"""
        for root, dirs, files in os.walk(self.vault_path):
            dirs[:] = [folder for folder in dirs if folder not in self.excluded_folders]
            for filename in files:
                if filename.endswith(".md"):
                    yield Path(root) / filename

    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """提取 YAML frontmatter。"""
        if not content.startswith("---"):
            return {}

        end_marker = "\n---"
        end_idx = content.find(end_marker, 3)
        if end_idx < 0:
            return {}

        frontmatter = content[3:end_idx]
        try:
            parsed = yaml.safe_load(frontmatter)
            if isinstance(parsed, dict):
                return parsed
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return {}
        return {}

    def _calculate_relevance(self, content: str, query_words: List[str]) -> float:
        """计算相关性分数。"""
        score = 0.0
        for word in query_words:
            count = content.count(word)
            if count > 0:
                score += min(count, 10)
        return score

    def _extract_snippet(self, content: str, query_words: List[str], context: int = 100) -> str:
        """提取包含查询词的片段。"""
        content_lower = content.lower()
        for word in query_words:
            idx = content_lower.find(word)
            if idx >= 0:
                start = max(0, idx - context)
                end = min(len(content), idx + len(word) + context)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
                return snippet

        if len(content) <= 200:
            return content
        return content[:200] + "..."
