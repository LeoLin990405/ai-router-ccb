"""NotebookLM CLI 封装 - 基于 notebooklm-py v0.3.2"""
from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, List, Optional

NOTEBOOKLM_BIN = "/Users/leo/.local/bin/notebooklm"


class NotebookLMClient:
    """NotebookLM CLI 客户端 (并行安全)。"""

    def __init__(self, timeout: int = 60, bin_path: Optional[str] = None):
        self.timeout = timeout
        self.bin = bin_path or NOTEBOOKLM_BIN
        self._check_cli()

    def _check_cli(self) -> None:
        """检查 notebooklm CLI 是否可用。"""
        try:
            subprocess.run(
                [self.bin, "--version"],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"notebooklm CLI not found at {self.bin}. "
                "Install: pip install notebooklm-py"
            ) from exc

    def _run(self, args: List[str], timeout: Optional[int] = None) -> str:
        """执行 notebooklm CLI 命令并返回 stdout。"""
        cmd = [self.bin] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout or self.timeout,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"notebooklm error: {result.stderr.strip() or 'command failed'}"
            )
        return result.stdout.strip()

    def _run_json(self, args: List[str], timeout: Optional[int] = None) -> Any:
        """执行命令并解析 JSON 输出。"""
        output = self._run(args + ["--json"], timeout=timeout)
        if not output:
            return None
        return json.loads(output)

    def check_auth(self) -> bool:
        """检查认证状态。"""
        try:
            result = self._run_json(["auth", "check"])
            if isinstance(result, dict):
                checks = result.get("checks", {})
                return all(checks.values()) if checks else False
            return False
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return False

    def list_notebooks(self) -> List[Dict[str, Any]]:
        """列出所有 notebooks。"""
        try:
            data = self._run_json(["list"])
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return []
        if isinstance(data, dict):
            return data.get("notebooks", [])
        if isinstance(data, list):
            return data
        return []

    def query(self, notebook_id: str, question: str) -> Dict[str, Any]:
        """查询特定 notebook (并行安全，使用 --notebook 参数)。"""
        try:
            result = self._run_json(
                ["ask", question, "--notebook", notebook_id],
                timeout=120,
            )
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            return {
                "answer": None,
                "error": str(exc),
                "references": [],
            }

        if isinstance(result, dict):
            return {
                "answer": result.get("answer"),
                "references": result.get("references", []),
                "conversation_id": result.get("conversation_id"),
            }
        return {
            "answer": None,
            "error": "unexpected response format",
            "references": [],
        }

    def search_notebooks(self, query: str) -> List[Dict[str, Any]]:
        """搜索最相关的 notebooks (通过标题关键词匹配)。"""
        notebooks = self.list_notebooks()
        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) >= 2]
        if not query_words:
            return notebooks[:5]

        scored: List[tuple] = []
        for nb in notebooks:
            title = (nb.get("title") or "").lower()
            score = 0
            for word in query_words:
                if word in title:
                    score += 1
            if score > 0:
                scored.append((score, nb))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [nb for _, nb in scored[:10]]

    def get_sources(self, notebook_id: str) -> List[Dict[str, Any]]:
        """获取 notebook 的所有来源。"""
        try:
            self._run(["use", notebook_id])
            result = self._run_json(["source", "list"])
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return []
        if isinstance(result, dict):
            return result.get("sources", [])
        if isinstance(result, list):
            return result
        return []

    def add_source(self, notebook_id: str, file_or_url: str) -> Dict[str, Any]:
        """添加来源到 notebook。"""
        self._run(["use", notebook_id])
        result = self._run_json(["source", "add", file_or_url])
        if isinstance(result, dict):
            return result
        return {"success": False, "error": "unexpected response"}

    def create_notebook(self, title: str) -> Dict[str, Any]:
        """创建新 notebook。"""
        result = self._run_json(["create", title])
        if isinstance(result, dict):
            return result
        return {"success": False, "error": "unexpected response"}
