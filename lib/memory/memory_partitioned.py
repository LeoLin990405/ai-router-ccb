#!/usr/bin/env python3
"""
CCB Memory with Table Partitioning
按月分表存储，自动管理
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


class CCBPartitionedMemory:
    """分表存储的记忆系统"""

    def __init__(self):
        self.ccb_dir = Path.home() / ".ccb"
        self.ccb_dir.mkdir(exist_ok=True)
        self.current_month = datetime.now().strftime("%Y%m")

    def _get_db_path(self, month: Optional[str] = None) -> Path:
        """获取指定月份的数据库路径"""
        month = month or self.current_month
        return self.ccb_dir / f"ccb_memory_{month}.db"

    def _init_db(self, db_path: Path):
        """初始化数据库表结构"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 创建表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                metadata TEXT,
                tokens INTEGER DEFAULT 0
            )
        ''')

        # 创建 FTS5 索引
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
                question, answer, provider,
                content='conversations',
                content_rowid='id'
            )
        ''')

        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON conversations(timestamp DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_provider ON conversations(provider)
        ''')

        conn.commit()
        conn.close()

    def record_conversation(self, provider: str, question: str, answer: str,
                          metadata: Optional[Dict[str, Any]] = None, tokens: int = 0) -> int:
        """记录对话到当前月份的数据库"""
        import json

        db_path = self._get_db_path()
        if not db_path.exists():
            self._init_db(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO conversations (timestamp, provider, question, answer, metadata, tokens)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), provider, question, answer,
              json.dumps(metadata or {}), tokens))

        rowid = cursor.lastrowid

        # 更新 FTS 索引
        cursor.execute('''
            INSERT INTO conversations_fts(rowid, question, answer, provider)
            VALUES (?, ?, ?, ?)
        ''', (rowid, question, answer, provider))

        conn.commit()
        conn.close()

        return rowid

    def search_conversations(self, keyword: str, limit: int = 10, months: int = 3) -> List[Dict]:
        """
        搜索对话（跨最近 N 个月）

        Args:
            keyword: 搜索关键词
            limit: 返回数量
            months: 搜索最近 N 个月的数据
        """
        results = []

        # 获取最近 N 个月的数据库文件
        db_files = sorted(self.ccb_dir.glob("ccb_memory_*.db"), reverse=True)[:months]

        for db_path in db_files:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT c.timestamp, c.provider, c.question, c.answer
                    FROM conversations c
                    JOIN conversations_fts fts ON c.id = fts.rowid
                    WHERE conversations_fts MATCH ?
                    ORDER BY c.timestamp DESC
                    LIMIT ?
                ''', (keyword, limit))

                results.extend([{
                    'timestamp': row[0],
                    'provider': row[1],
                    'question': row[2],
                    'answer': row[3]
                } for row in cursor.fetchall()])

                conn.close()

                if len(results) >= limit:
                    break

            except sqlite3.OperationalError:
                continue

        return results[:limit]

    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """获取最近的对话"""
        db_path = self._get_db_path()

        if not db_path.exists():
            return []

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT timestamp, provider, question, answer
            FROM conversations
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        results = [{
            'timestamp': row[0],
            'provider': row[1],
            'question': row[2],
            'answer': row[3]
        } for row in cursor.fetchall()]

        conn.close()
        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取所有分表的统计信息"""
        db_files = list(self.ccb_dir.glob("ccb_memory_*.db"))

        total_conversations = 0
        total_size = 0
        partitions = []

        for db_path in sorted(db_files):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM conversations")
            count = cursor.fetchone()[0]

            size = db_path.stat().st_size / 1024 / 1024  # MB

            month = db_path.stem.replace("ccb_memory_", "")
            partitions.append({
                'month': month,
                'count': count,
                'size_mb': round(size, 2),
                'path': str(db_path)
            })

            total_conversations += count
            total_size += size

            conn.close()

        return {
            'total_conversations': total_conversations,
            'total_size_mb': round(total_size, 2),
            'partitions': partitions
        }

    def cleanup_old_partitions(self, keep_months: int = 12):
        """删除超过 N 个月的数据库文件"""
        db_files = sorted(self.ccb_dir.glob("ccb_memory_*.db"), reverse=True)

        deleted = []
        for db_path in db_files[keep_months:]:
            size = db_path.stat().st_size / 1024 / 1024
            deleted.append({
                'month': db_path.stem.replace("ccb_memory_", ""),
                'size_mb': round(size, 2)
            })
            db_path.unlink()

        return deleted


def main():
    import sys

    memory = CCBPartitionedMemory()

    if len(sys.argv) < 2:
        print("用法: python3 memory_partitioned.py <command>")
        print("\n命令:")
        print("  stats              - 查看分表统计")
        print("  recent [N]         - 查看最近 N 条记录")
        print("  search <keyword>   - 搜索对话")
        print("  cleanup [months]   - 清理超过 N 个月的数据")
        return

    command = sys.argv[1]

    if command == "stats":
        stats = memory.get_stats()
        print(f"\n📊 CCB Memory 分表统计")
        print("=" * 60)
        print(f"总对话数: {stats['total_conversations']}")
        print(f"总大小:   {stats['total_size_mb']} MB")
        print(f"\n分表详情:")
        for p in stats['partitions']:
            print(f"  {p['month']}: {p['count']:>6} 条, {p['size_mb']:>6} MB")

    elif command == "recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        results = memory.get_recent_conversations(limit)

        print(f"\n🕒 最近 {len(results)} 条对话:")
        for r in results:
            print(f"\n[{r['provider']}] {r['timestamp']}")
            print(f"Q: {r['question'][:80]}...")

    elif command == "search":
        if len(sys.argv) < 3:
            print("❌ 请提供搜索关键词")
            return

        keyword = sys.argv[2]
        results = memory.search_conversations(keyword)

        print(f"\n🔍 找到 {len(results)} 条结果:")
        for r in results:
            print(f"\n[{r['provider']}] {r['timestamp']}")
            print(f"Q: {r['question'][:80]}...")

    elif command == "cleanup":
        keep_months = int(sys.argv[2]) if len(sys.argv) > 2 else 12
        deleted = memory.cleanup_old_partitions(keep_months)

        if deleted:
            print(f"\n🗑️  已删除 {len(deleted)} 个旧分表:")
            for d in deleted:
                print(f"  {d['month']}: {d['size_mb']} MB")
        else:
            print("✅ 无需清理")


if __name__ == "__main__":
    main()
