#!/usr/bin/env python3
"""
Migration script: Rebuild FTS5 indexes with trigram tokenizer
Fixes Issue #9: FTS5 Chinese tokenization optimization
"""

import sqlite3
import sys
from pathlib import Path


def _emit(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")

def migrate_fts5_trigram(db_path: str):
    """Rebuild FTS5 indexes with trigram tokenizer for better Chinese support"""

    _emit(f"🔧 Migrating FTS5 indexes in: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Step 1: Drop old FTS5 tables
        _emit("\n📦 Step 1: Dropping old FTS5 tables...")
        cursor.execute("DROP TABLE IF EXISTS messages_fts;")
        cursor.execute("DROP TABLE IF EXISTS observations_fts;")
        _emit("   ✅ Old FTS5 tables dropped")

        # Step 2: Recreate messages_fts with trigram tokenizer
        _emit("\n📦 Step 2: Creating messages_fts with trigram tokenizer...")
        cursor.execute("""
            CREATE VIRTUAL TABLE messages_fts USING fts5(
                content,
                provider,
                skills_used,
                content='messages',
                content_rowid='rowid',
                tokenize='trigram'
            );
        """)
        _emit("   ✅ messages_fts created with trigram tokenizer")

        # Step 3: Recreate observations_fts with trigram tokenizer
        _emit("\n📦 Step 3: Creating observations_fts with trigram tokenizer...")
        cursor.execute("""
            CREATE VIRTUAL TABLE observations_fts USING fts5(
                content,
                tags,
                content='observations',
                content_rowid='rowid',
                tokenize='trigram'
            );
        """)
        _emit("   ✅ observations_fts created with trigram tokenizer")

        # Step 4: Rebuild messages_fts index from existing data
        _emit("\n📦 Step 4: Rebuilding messages_fts index...")
        cursor.execute("SELECT COUNT(*) FROM messages;")
        message_count = cursor.fetchone()[0]
        _emit(f"   Found {message_count} messages to index")

        cursor.execute("""
            INSERT INTO messages_fts(rowid, content, provider, skills_used)
            SELECT rowid, content, provider, skills_used FROM messages;
        """)
        _emit(f"   ✅ Indexed {message_count} messages")

        # Step 5: Rebuild observations_fts index from existing data
        _emit("\n📦 Step 5: Rebuilding observations_fts index...")
        cursor.execute("SELECT COUNT(*) FROM observations;")
        obs_count = cursor.fetchone()[0]
        _emit(f"   Found {obs_count} observations to index")

        if obs_count > 0:
            cursor.execute("""
                INSERT INTO observations_fts(rowid, content, tags)
                SELECT rowid, content, tags FROM observations;
            """)
            _emit(f"   ✅ Indexed {obs_count} observations")
        else:
            _emit(f"   ⏭️  No observations to index")

        # Step 6: Verify FTS5 search
        _emit("\n📦 Step 6: Verifying trigram search...")
        cursor.execute("SELECT COUNT(*) FROM messages WHERE content LIKE '%购物车%';")
        like_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM messages_fts WHERE messages_fts MATCH '购物车';")
        match_count = cursor.fetchone()[0]

        _emit(f"   LIKE query:  {like_count} results")
        _emit(f"   MATCH query: {match_count} results")

        if match_count >= like_count:
            _emit(f"   ✅ FTS5 search improved! Found {match_count}/{like_count} messages")
        else:
            _emit(f"   ⚠️  FTS5 still finding {match_count}/{like_count} messages")

        # Commit changes
        conn.commit()
        _emit("\n✅ Migration completed successfully!")

        return True

    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        _emit(f"\n❌ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    # Default database path
    db_path = Path.home() / ".ccb" / "ccb_memory.db"

    # Allow custom path from command line
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])

    if not db_path.exists():
        _emit(f"❌ Database not found: {db_path}")
        sys.exit(1)

    success = migrate_fts5_trigram(str(db_path))
    sys.exit(0 if success else 1)
