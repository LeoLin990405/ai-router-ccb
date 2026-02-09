"""Knowledge Router - 统一知识路由器。"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from lib.common.logging import get_logger

from .index_manager import IndexManager
from .notebooklm_client import NotebookLMClient
from .obsidian_search import ObsidianSearch


DEFAULT_CONFIG: Dict[str, Any] = {
    "knowledge": {
        "db_path": "~/.local/share/codex-dual/data/knowledge_index.db",
        "obsidian": {
            "vault_path": "~/Desktop/新笔记",
            "excluded_folders": [".obsidian", ".trash", "templates"],
        },
        "notebooklm": {
            "bin_path": "/Users/leo/.local/bin/notebooklm",
            "timeout": 60,
            "max_retries": 2,
        },
        "cache": {
            "enabled": True,
            "ttl": 86400,
            "max_entries": 1000,
        },
        "routing": {
            "default_source": "auto",
            "local_first": True,
            "confidence_threshold": 0.7,
        },
    }
}


logger = get_logger("knowledge.router")


class KnowledgeRouter:
    """统一知识路由器。"""

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        knowledge_conf = self.config["knowledge"]

        self.index = IndexManager(knowledge_conf["db_path"])

        self.notebooklm: Optional[NotebookLMClient] = None
        nlm_conf = knowledge_conf.get("notebooklm", {})
        try:
            self.notebooklm = NotebookLMClient(
                timeout=int(nlm_conf.get("timeout", 60)),
                bin_path=nlm_conf.get("bin_path"),
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            logger.warning("NotebookLM not available: %s", exc)

        self.obsidian: Optional[ObsidianSearch] = None
        obsidian_conf = knowledge_conf.get("obsidian", {})
        vault_path = str(obsidian_conf.get("vault_path", "")).strip()
        if vault_path:
            expanded_vault = Path(vault_path).expanduser()
            if expanded_vault.exists() and expanded_vault.is_dir():
                try:
                    self.obsidian = ObsidianSearch(
                        vault_path=vault_path,
                        excluded_folders=list(obsidian_conf.get("excluded_folders", [])),
                    )
                except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
                    logger.warning("Obsidian init failed: %s", exc)

        logger.info(
            "KnowledgeRouter initialized NotebookLM=%s Obsidian=%s",
            bool(self.notebooklm),
            bool(self.obsidian),
        )

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        path = Path(config_path).expanduser() if config_path else Path.home() / ".local/share/codex-dual/config/knowledge.yaml"
        if not path.exists():
            return DEFAULT_CONFIG.copy()

        try:
            with path.open("r", encoding="utf-8") as file:
                loaded = yaml.safe_load(file) or {}
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return DEFAULT_CONFIG.copy()

        merged = DEFAULT_CONFIG.copy()
        merged_knowledge = dict(DEFAULT_CONFIG["knowledge"])
        loaded_knowledge = loaded.get("knowledge") if isinstance(loaded, dict) else None
        if isinstance(loaded_knowledge, dict):
            for key, default_value in DEFAULT_CONFIG["knowledge"].items():
                if key not in loaded_knowledge:
                    merged_knowledge[key] = default_value
                elif isinstance(default_value, dict) and isinstance(loaded_knowledge[key], dict):
                    merged_knowledge[key] = {**default_value, **loaded_knowledge[key]}
                else:
                    merged_knowledge[key] = loaded_knowledge[key]
        merged["knowledge"] = merged_knowledge
        return merged

    def query(
        self,
        question: str,
        source: str = "auto",
        notebook_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """统一查询接口。"""
        source = source or "auto"
        cache_conf = self.config["knowledge"].get("cache", {})
        cache_enabled = bool(cache_conf.get("enabled", True))

        if use_cache and cache_enabled:
            query_hash = self._hash_query(question, source, notebook_id)
            cached = self.index.get_cached(query_hash)
            if cached:
                return {
                    "answer": cached.get("answer"),
                    "source": cached.get("source", source),
                    "references": cached.get("references", []),
                    "cached": True,
                    "confidence": 1.0,
                }

        if source == "auto":
            result = self._auto_route(question=question, notebook_id=notebook_id)
        elif source == "notebooklm":
            result = self._query_notebooklm(question=question, notebook_id=notebook_id)
        elif source == "obsidian":
            result = self._query_obsidian(question=question)
        else:
            return {
                "answer": None,
                "source": source,
                "references": [],
                "confidence": 0.0,
                "error": f"Unknown source: {source}",
                "cached": False,
            }

        if use_cache and result.get("answer") and cache_enabled:
            query_hash = self._hash_query(question, source, notebook_id)
            self.index.set_cached(
                query_hash=query_hash,
                source=result.get("source", source),
                question=question,
                answer=result["answer"],
                references=result.get("references", []),
                ttl=int(cache_conf.get("ttl", 86400)),
            )

        result["cached"] = False
        if "references" not in result:
            result["references"] = []
        if "confidence" not in result:
            result["confidence"] = 0.0
        return result

    def _auto_route(self, question: str, notebook_id: Optional[str] = None) -> Dict[str, Any]:
        routing_conf = self.config["knowledge"].get("routing", {})

        if notebook_id and self.notebooklm:
            return self._query_notebooklm(question=question, notebook_id=notebook_id)

        if routing_conf.get("local_first", True) and self.obsidian:
            local_result = self._query_obsidian(question)
            if local_result.get("confidence", 0.0) >= float(routing_conf.get("confidence_threshold", 0.7)):
                return local_result

        if self.notebooklm:
            return self._query_notebooklm(question=question, notebook_id=notebook_id)

        if self.obsidian:
            return self._query_obsidian(question)

        return {
            "answer": None,
            "source": "none",
            "references": [],
            "confidence": 0.0,
            "error": "No knowledge source available",
        }

    def _query_notebooklm(self, question: str, notebook_id: Optional[str] = None) -> Dict[str, Any]:
        if not self.notebooklm:
            return {
                "answer": None,
                "source": "notebooklm",
                "references": [],
                "confidence": 0.0,
                "error": "NotebookLM not available",
            }

        try:
            selected_notebook = notebook_id
            if not selected_notebook:
                # 1. 先从本地索引搜索
                best = self.index.find_best_notebook(question)
                if best:
                    selected_notebook = best["id"]

            if not selected_notebook:
                # 2. 在线搜索
                notebooks = self.notebooklm.search_notebooks(question)
                if notebooks:
                    selected_notebook = notebooks[0].get("id")

            if not selected_notebook:
                return {
                    "answer": None,
                    "source": "notebooklm",
                    "references": [],
                    "confidence": 0.0,
                    "error": "No relevant notebook found",
                }

            result = self.notebooklm.query(selected_notebook, question)
            self.index.record_query(selected_notebook)

            answer = result.get("answer")
            return {
                "answer": answer,
                "source": "notebooklm",
                "notebook_id": selected_notebook,
                "references": result.get("references", []),
                "confidence": 0.9 if answer else 0.0,
                "error": result.get("error"),
            }
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            return {
                "answer": None,
                "source": "notebooklm",
                "references": [],
                "confidence": 0.0,
                "error": str(exc),
            }

    def _query_obsidian(self, question: str) -> Dict[str, Any]:
        if not self.obsidian:
            return {
                "answer": None,
                "source": "obsidian",
                "references": [],
                "confidence": 0.0,
                "error": "Obsidian not available",
            }

        try:
            results = self.obsidian.search(question, limit=5)
            if not results:
                return {
                    "answer": None,
                    "source": "obsidian",
                    "references": [],
                    "confidence": 0.0,
                }

            top_result = results[0]
            note = self.obsidian.get_note(top_result["path"])
            confidence = min(float(top_result.get("score", 0.0)) / 50.0, 1.0)

            answer = top_result.get("snippet")
            if note and note.get("content"):
                answer = str(note["content"])[:2000]

            references: List[Dict[str, Any]] = []
            for item in results:
                references.append(
                    {
                        "title": item.get("title"),
                        "path": item.get("path"),
                        "score": item.get("score", 0),
                    }
                )

            return {
                "answer": answer,
                "source": "obsidian",
                "references": references,
                "confidence": confidence,
            }
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            return {
                "answer": None,
                "source": "obsidian",
                "references": [],
                "confidence": 0.0,
                "error": str(exc),
            }

    def _hash_query(self, question: str, source: str, notebook_id: Optional[str] = None) -> str:
        key = f"{question}:{source}:{notebook_id or ''}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def sync_notebooklm(self) -> int:
        """同步 NotebookLM notebooks 到本地索引。"""
        if not self.notebooklm:
            return 0

        notebooks = self.notebooklm.list_notebooks()
        for notebook in notebooks:
            if isinstance(notebook, dict) and notebook.get("id"):
                self.index.upsert_notebook(notebook)
        return len(notebooks)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息。"""
        return {
            "index": self.index.get_stats(),
            "notebooklm_available": self.notebooklm is not None,
            "obsidian_available": self.obsidian is not None,
        }

    def check_auth(self) -> bool:
        """检查 NotebookLM 认证状态。"""
        if not self.notebooklm:
            return False
        return self.notebooklm.check_auth()

    def create_notebook(self, title: str) -> Dict[str, Any]:
        """创建 NotebookLM notebook。"""
        if not self.notebooklm:
            return {"success": False, "error": "NotebookLM not available"}
        result = self.notebooklm.create_notebook(title)
        # 同步到本地索引
        if result.get("id"):
            self.index.upsert_notebook(result)
        return result

    def add_source(self, notebook_id: str, file_or_url: str) -> Dict[str, Any]:
        """添加来源到 notebook。"""
        if not self.notebooklm:
            return {"success": False, "error": "NotebookLM not available"}
        return self.notebooklm.add_source(notebook_id, file_or_url)

    def search_notebooks_online(self, query: str) -> List[Dict[str, Any]]:
        """搜索 notebooks（先本地索引，后在线）。"""
        local_results = self.index.find_notebooks_by_keyword(query)
        if local_results:
            return local_results
        if self.notebooklm:
            return self.notebooklm.search_notebooks(query)
        return []
