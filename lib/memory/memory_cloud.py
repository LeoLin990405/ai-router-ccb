#!/usr/bin/env python3
"""
CCB Memory Cloud Migration
本地数据库 → 云端数据库 迁移工具
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import Literal


class CCBCloudMigration:
    """云端数据库迁移工具"""

    def __init__(self, cloud_type: Literal["firebase", "supabase", "planetscale"]):
        self.cloud_type = cloud_type
        self.local_db = Path.home() / ".ccb" / "ccb_memory.db"

        if cloud_type == "firebase":
            self._init_firebase()
        elif cloud_type == "supabase":
            self._init_supabase()
        elif cloud_type == "planetscale":
            self._init_planetscale()

    def _init_firebase(self):
        """初始化 Firebase"""
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            cred_path = Path.home() / ".ccb" / "firebase-key.json"
            if not cred_path.exists():
                print("❌ 未找到 Firebase 凭证文件: ~/.ccb/firebase-key.json")
                print("📖 获取凭证: https://console.firebase.google.com/")
                raise FileNotFoundError

            cred = credentials.Certificate(str(cred_path))
            firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            print("✅ Firebase 已连接")

        except ImportError:
            print("❌ 请安装: pip3 install firebase-admin")
            raise

    def _init_supabase(self):
        """初始化 Supabase"""
        try:
            from supabase import create_client, Client

            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")

            if not url or not key:
                print("❌ 请设置环境变量:")
                print("  export SUPABASE_URL='https://xxx.supabase.co'")
                print("  export SUPABASE_KEY='your-anon-key'")
                raise ValueError

            self.db: Client = create_client(url, key)
            print("✅ Supabase 已连接")

        except ImportError:
            print("❌ 请安装: pip3 install supabase")
            raise

    def _init_planetscale(self):
        """初始化 PlanetScale（MySQL）"""
        try:
            import pymysql

            host = os.environ.get("PLANETSCALE_HOST")
            user = os.environ.get("PLANETSCALE_USER")
            password = os.environ.get("PLANETSCALE_PASSWORD")
            database = os.environ.get("PLANETSCALE_DATABASE")

            if not all([host, user, password, database]):
                print("❌ 请设置环境变量:")
                print("  export PLANETSCALE_HOST='xxx.psdb.cloud'")
                print("  export PLANETSCALE_USER='...'")
                print("  export PLANETSCALE_PASSWORD='...'")
                print("  export PLANETSCALE_DATABASE='...'")
                raise ValueError

            self.db = pymysql.connect(
                host=host,
                user=user,
                password=password,
                database=database,
                ssl={'ssl': True}
            )
            print("✅ PlanetScale 已连接")

        except ImportError:
            print("❌ 请安装: pip3 install pymysql")
            raise

    def migrate_to_cloud(self, batch_size: int = 100, dry_run: bool = False):
        """
        迁移本地数据到云端

        Args:
            batch_size: 批量上传大小
            dry_run: 只测试不上传
        """
        if not self.local_db.exists():
            print("❌ 本地数据库不存在")
            return

        # 读取本地数据
        conn = sqlite3.connect(self.local_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_count = cursor.fetchone()[0]

        print(f"\n📦 准备迁移 {total_count} 条记录...")

        if dry_run:
            print("🔍 DRY RUN 模式 - 不会实际上传")

        cursor.execute('''
            SELECT id, timestamp, provider, question, answer, metadata, tokens
            FROM conversations
            ORDER BY id
        ''')

        migrated = 0
        failed = 0

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break

            if dry_run:
                migrated += len(rows)
                print(f"  ✓ 模拟迁移 batch {migrated}/{total_count}")
                continue

            # 上传到云端
            try:
                if self.cloud_type == "firebase":
                    self._upload_firebase_batch(rows)
                elif self.cloud_type == "supabase":
                    self._upload_supabase_batch(rows)
                elif self.cloud_type == "planetscale":
                    self._upload_planetscale_batch(rows)

                migrated += len(rows)
                print(f"  ✓ 已迁移 {migrated}/{total_count} ({migrated/total_count*100:.1f}%)")

            except Exception as e:
                failed += len(rows)
                print(f"  ✗ 批次上传失败: {e}")

        conn.close()

        print(f"\n{'=' * 60}")
        print(f"✅ 迁移完成:")
        print(f"  成功: {migrated}/{total_count}")
        if failed > 0:
            print(f"  失败: {failed}/{total_count}")

    def _upload_firebase_batch(self, rows):
        """批量上传到 Firebase"""
        batch = self.db.batch()

        for row in rows:
            doc_ref = self.db.collection('conversations').document(str(row[0]))
            batch.set(doc_ref, {
                'timestamp': row[1],
                'provider': row[2],
                'question': row[3],
                'answer': row[4],
                'metadata': row[5],
                'tokens': row[6]
            })

        batch.commit()

    def _upload_supabase_batch(self, rows):
        """批量上传到 Supabase"""
        data = [{
            'id': row[0],
            'timestamp': row[1],
            'provider': row[2],
            'question': row[3],
            'answer': row[4],
            'metadata': row[5],
            'tokens': row[6]
        } for row in rows]

        self.db.table('conversations').insert(data).execute()

    def _upload_planetscale_batch(self, rows):
        """批量上传到 PlanetScale"""
        cursor = self.db.cursor()

        cursor.executemany('''
            INSERT INTO conversations (id, timestamp, provider, question, answer, metadata, tokens)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE timestamp=VALUES(timestamp)
        ''', rows)

        self.db.commit()

    def verify_migration(self):
        """验证迁移结果"""
        # 本地数据统计
        conn = sqlite3.connect(self.local_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), provider FROM conversations GROUP BY provider")
        local_stats = dict(cursor.fetchall())
        conn.close()

        print(f"\n🔍 验证迁移结果:")
        print(f"{'=' * 60}")
        print(f"{'Provider':<15} {'本地':<10} {'云端':<10} {'状态'}")
        print(f"{'-' * 60}")

        # 云端数据统计
        if self.cloud_type == "firebase":
            for provider, local_count in local_stats.items():
                docs = self.db.collection('conversations')\
                    .where('provider', '==', provider)\
                    .stream()
                cloud_count = sum(1 for _ in docs)

                status = "✅" if cloud_count == local_count else "❌"
                print(f"{provider:<15} {local_count:<10} {cloud_count:<10} {status}")

        elif self.cloud_type == "supabase":
            for provider, local_count in local_stats.items():
                result = self.db.table('conversations')\
                    .select('*', count='exact')\
                    .eq('provider', provider)\
                    .execute()
                cloud_count = result.count

                status = "✅" if cloud_count == local_count else "❌"
                print(f"{provider:<15} {local_count:<10} {cloud_count:<10} {status}")


def main():
    import sys

    if len(sys.argv) < 2:
        print("""
CCB Memory 云端迁移工具

用法:
  python3 memory_cloud.py <cloud-type> <command> [options]

云端类型:
  firebase      - Google Firebase Firestore
  supabase      - Supabase PostgreSQL
  planetscale   - PlanetScale MySQL

命令:
  migrate       - 开始迁移
  verify        - 验证迁移结果
  dry-run       - 测试迁移（不上传）

示例:
  # 迁移到 Firebase
  python3 memory_cloud.py firebase migrate

  # 测试迁移
  python3 memory_cloud.py supabase dry-run

  # 验证结果
  python3 memory_cloud.py firebase verify
""")
        return

    cloud_type = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "migrate"

    try:
        migration = CCBCloudMigration(cloud_type)

        if command == "migrate":
            migration.migrate_to_cloud(batch_size=100, dry_run=False)
            migration.verify_migration()

        elif command == "dry-run":
            migration.migrate_to_cloud(batch_size=100, dry_run=True)

        elif command == "verify":
            migration.verify_migration()

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        return


if __name__ == "__main__":
    main()
