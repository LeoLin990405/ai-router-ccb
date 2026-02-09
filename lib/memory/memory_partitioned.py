#!/usr/bin/env python3
"""
CCB Memory compatibility layer (single DB, month-aware views)

历史上该模块按月拆分为多个 SQLite 文件。
当前实现已统一到单库 `~/.ccb/ccb_memory.db`，通过 timestamp 做月维度统计/过滤。
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional


def _emit(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")


class CCBPartitionedMemory:
    """兼容旧接口的单库记忆系统。"""

    def __init__(self):
        self.ccb_dir = Path.home() / ".ccb"
        self.ccb_dir.mkdir(exist_ok=True)
        self.db_path = self.ccb_dir / "ccb_memory.db"
        self.current_month = datetime.now().strftime("%Y%m")
        self._init_db(self.db_path)

    def _get_db_path(self, month: Optional[str] = None) -> Path:
        """兼容旧接口：始终返回统一数据库路径。"""
        _ = month
        return self.db_path

    def _init_db(self, db_path: Path):
        """初始化数据库表结构。"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                metadata TEXT,
                tokens INTEGER DEFAULT 0
            )
        """
        )

        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
                question, answer, provider,
                content='conversations',
                content_rowid='id'
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_timestamp
            ON conversations(timestamp DESC)
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_provider
            ON conversations(provider)
        """
        )

        conn.commit()
        conn.close()

    @staticmethod
    def _cutoff_days(months: int) -> str:
        days = max(1, months) * 30
        return (datetime.now() - timedelta(days=days)).isoformat()

    def record_conversation(
        self,
        provider: str,
        question: str,
        answer: str,
        metadata: Optional[Dict[str, Any]] = None,
        tokens: int = 0,
    ) -> int:
        """记录对话到统一数据库。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO conversations (timestamp, provider, question, answer, metadata, tokens)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (datetime.now().isoformat(), provider, question, answer, json.dumps(metadata or {}), tokens),
        )

        rowid = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO conversations_fts(rowid, question, answer, provider)
            VALUES (?, ?, ?, ?)
        """,
            (rowid, question, answer, provider),
        )

        conn.commit()
        conn.close()
        return rowid

    def search_conversations(self, keyword: str, limit: int = 10, months: int = 3) -> List[Dict]:
        """
        搜索对话（最近 N 个月范围内）。

        Args:
            keyword: 搜索关键词
            limit: 返回数量
            months: 搜索最近 N 个月的数据
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cutoff = self._cutoff_days(months)
            cursor.execute(
                """
                SELECT c.timestamp, c.provider, c.question, c.answer
                FROM conversations c
                JOIN conversations_fts fts ON c.id = fts.rowid
                WHERE conversations_fts MATCH ? AND c.timestamp >= ?
                ORDER BY c.timestamp DESC
                LIMIT ?
            """,
                (keyword, cutoff, limit),
            )

            return [
                {
                    "timestamp": row[0],
                    "provider": row[1],
                    "question": row[2],
                    "answer": row[3],
                }
                for row in cursor.fetchall()
            ]
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """获取最近的对话。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT timestamp, provider, question, answer
            FROM conversations
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )

        results = [
            {
                "timestamp": row[0],
                "provider": row[1],
                "question": row[2],
                "answer": row[3],
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取统一数据库的月度统计信息。"""
        if not self.db_path.exists():
            return {"total_conversations": 0, "total_size_mb": 0.0, "partitions": []}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_conversations = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT strftime('%Y%m', timestamp) AS month, COUNT(*)
            FROM conversations
            GROUP BY month
            ORDER BY month
        """
        )
        by_month = cursor.fetchall()
        conn.close()

        total_size = self.db_path.stat().st_size / 1024 / 1024

        partitions = [
            {
                "month": month or "unknown",
                "count": count,
                "size_mb": round(total_size, 2),
                "path": str(self.db_path),
            }
            for month, count in by_month
        ]

        return {
            "total_conversations": total_conversations,
            "total_size_mb": round(total_size, 2),
            "partitions": partitions,
        }

    def cleanup_old_partitions(self, keep_months: int = 12):
        """
        兼容旧接口：删除统一库中超过 N 个月的数据。

        Returns:
            List[Dict]: 兼容旧返回格式
        """
        keep_months = max(1, keep_months)
        cutoff = self._cutoff_days(keep_months)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT strftime('%Y%m', timestamp) AS month, COUNT(*)
            FROM conversations
            WHERE timestamp < ?
            GROUP BY month
            ORDER BY month
        """,
            (cutoff,),
        )
        old_months = cursor.fetchall()

        if not old_months:
            conn.close()
            return []

        cursor.execute("DELETE FROM conversations WHERE timestamp < ?", (cutoff,))
        cursor.execute("INSERT INTO conversations_fts(conversations_fts) VALUES('rebuild')")
        conn.commit()
        conn.close()

        return [
            {
                "month": month or "unknown",
                "size_mb": 0.0,
            }
            for month, _count in old_months
        ]


def main():
    memory = CCBPartitionedMemory()

    if len(sys.argv) < 2:
        _emit("用法: python3 memory_partitioned.py <command>")
        _emit("\n命令:")
        _emit("  stats              - 查看分区统计（单库月视图）")
        _emit("  recent [N]         - 查看最近 N 条记录")
        _emit("  search <keyword>   - 搜索对话")
        _emit("  cleanup [months]   - 清理超过 N 个月的数据")
        return

    command = sys.argv[1]

    if command == "stats":
        stats = memory.get_stats()
        _emit("\n📊 CCB Memory 统计（统一数据库）")
        _emit("=" * 60)
        _emit(f"总对话数: {stats['total_conversations']}")
        _emit(f"总大小:   {stats['total_size_mb']} MB")
        _emit("\n月度详情:")
        for p in stats["partitions"]:
            _emit(f"  {p['month']}: {p['count']:>6} 条")

    elif command == "recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        results = memory.get_recent_conversations(limit)

        _emit(f"\n🕒 最近 {len(results)} 条对话:")
        for r in results:
            _emit(f"\n[{r['provider']}] {r['timestamp']}")
            _emit(f"Q: {r['question'][:80]}...")

    elif command == "search":
        if len(sys.argv) < 3:
            _emit("❌ 请提供搜索关键词")
            return

        keyword = sys.argv[2]
        results = memory.search_conversations(keyword)

        _emit(f"\n🔍 找到 {len(results)} 条结果:")
        for r in results:
            _emit(f"\n[{r['provider']}] {r['timestamp']}")
            _emit(f"Q: {r['question'][:80]}...")

    elif command == "cleanup":
        keep_months = int(sys.argv[2]) if len(sys.argv) > 2 else 12
        deleted = memory.cleanup_old_partitions(keep_months)

        if deleted:
            _emit(f"\n🗑️  已清理 {len(deleted)} 个月份的旧数据:")
            for d in deleted:
                _emit(f"  {d['month']}")
        else:
            _emit("✅ 无需清理")


if __name__ == "__main__":
    main()
