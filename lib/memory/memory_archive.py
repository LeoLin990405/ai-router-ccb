#!/usr/bin/env python3
"""
CCB Memory Archive System
自动归档旧数据，保持数据库轻量
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import gzip
import shutil


class CCBMemoryArchive:
    def __init__(self):
        self.ccb_dir = Path.home() / ".ccb"
        self.active_db = self.ccb_dir / "ccb_memory.db"
        self.archive_dir = self.ccb_dir / "archives"
        self.archive_dir.mkdir(exist_ok=True)

    def get_db_size(self) -> tuple:
        """获取数据库大小和记录数"""
        conn = sqlite3.connect(self.active_db)
        cursor = conn.cursor()

        # 获取记录数
        cursor.execute("SELECT COUNT(*) FROM conversations")
        count = cursor.fetchone()[0]

        # 获取文件大小
        size_bytes = self.active_db.stat().st_size
        size_mb = size_bytes / 1024 / 1024

        conn.close()
        return count, size_mb

    def archive_old_data(self, days_to_keep: int = 90, compress: bool = True):
        """
        归档旧数据到单独文件

        Args:
            days_to_keep: 保留最近 N 天的数据
            compress: 是否压缩归档文件
        """
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()

        conn = sqlite3.connect(self.active_db)
        cursor = conn.cursor()

        # 查询需要归档的数据
        cursor.execute('''
            SELECT * FROM conversations
            WHERE timestamp < ?
            ORDER BY timestamp
        ''', (cutoff_date,))

        old_records = cursor.fetchall()

        if not old_records:
            print(f"✅ 无需归档，所有记录都在最近 {days_to_keep} 天内")
            conn.close()
            return

        # 创建归档文件
        archive_name = f"archive_{datetime.now().strftime('%Y%m')}.db"
        archive_path = self.archive_dir / archive_name

        # 创建归档数据库
        archive_conn = sqlite3.connect(archive_path)
        archive_cursor = archive_conn.cursor()

        # 创建表结构（复制）
        archive_cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                metadata TEXT,
                tokens INTEGER DEFAULT 0
            )
        ''')

        # 插入归档数据
        archive_cursor.executemany('''
            INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', old_records)

        archive_conn.commit()
        archive_conn.close()

        # 从主数据库删除已归档数据
        cursor.execute('DELETE FROM conversations WHERE timestamp < ?', (cutoff_date,))

        # 重建 FTS 索引
        cursor.execute("INSERT INTO conversations_fts(conversations_fts) VALUES('rebuild')")

        # 优化数据库
        cursor.execute('VACUUM')

        conn.commit()
        conn.close()

        # 压缩归档文件（可选）
        if compress:
            with open(archive_path, 'rb') as f_in:
                with gzip.open(f"{archive_path}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            archive_path.unlink()  # 删除未压缩版本
            archive_path = Path(f"{archive_path}.gz")

        archive_size = archive_path.stat().st_size / 1024 / 1024

        print(f"✅ 已归档 {len(old_records)} 条记录")
        print(f"📁 归档文件: {archive_path.name} ({archive_size:.2f} MB)")
        print(f"🗑️  已从主数据库删除")

    def search_archives(self, keyword: str, limit: int = 10):
        """在归档文件中搜索"""
        results = []

        for archive_file in self.archive_dir.glob("archive_*.db*"):
            # 如果是压缩文件，先解压
            if archive_file.suffix == '.gz':
                import tempfile
                with gzip.open(archive_file, 'rb') as f_in:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        temp_db = f_out.name
            else:
                temp_db = archive_file

            # 搜索归档数据库
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT timestamp, provider, question, answer
                FROM conversations
                WHERE question LIKE ? OR answer LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (f'%{keyword}%', f'%{keyword}%', limit))

            results.extend([{
                'timestamp': row[0],
                'provider': row[1],
                'question': row[2],
                'answer': row[3],
                'source': 'archive'
            } for row in cursor.fetchall()])

            conn.close()

            # 清理临时文件
            if archive_file.suffix == '.gz':
                Path(temp_db).unlink()

        return results[:limit]

    def get_stats(self):
        """获取存储统计"""
        active_count, active_size = self.get_db_size()

        # 统计归档
        archive_files = list(self.archive_dir.glob("archive_*"))
        archive_count = len(archive_files)
        archive_size = sum(f.stat().st_size for f in archive_files) / 1024 / 1024

        print(f"""
📊 CCB Memory 存储统计
{'=' * 50}

活跃数据库:
  记录数:    {active_count}
  大小:      {active_size:.2f} MB
  位置:      {self.active_db}

归档文件:
  数量:      {archive_count}
  总大小:    {archive_size:.2f} MB
  位置:      {self.archive_dir}

总计:
  记录数:    约 {active_count} + 归档
  总大小:    {active_size + archive_size:.2f} MB
""")


def main():
    import sys

    archive = CCBMemoryArchive()

    if len(sys.argv) < 2:
        print("用法: python3 memory_archive.py <command> [options]")
        print("\n命令:")
        print("  stats              - 查看存储统计")
        print("  archive [days]     - 归档 N 天前的数据（默认 90）")
        print("  search <keyword>   - 搜索归档数据")
        return

    command = sys.argv[1]

    if command == "stats":
        archive.get_stats()

    elif command == "archive":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        archive.archive_old_data(days_to_keep=days)
        archive.get_stats()

    elif command == "search":
        if len(sys.argv) < 3:
            print("❌ 请提供搜索关键词")
            return
        keyword = sys.argv[2]
        results = archive.search_archives(keyword)

        print(f"\n🔍 在归档中找到 {len(results)} 条结果:")
        for r in results:
            print(f"\n[{r['provider']}] {r['timestamp']}")
            print(f"Q: {r['question'][:100]}...")
            print(f"A: {r['answer'][:100]}...")


if __name__ == "__main__":
    main()
