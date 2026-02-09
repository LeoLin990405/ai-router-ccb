#!/usr/bin/env python3
"""
CCB Memory System - Lightweight implementation using existing claude-mem database

Uses the claude-mem SQLite database for memory, plus a simple registry system.
"""
import sqlite3
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


def _emit(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")


class CCBLightMemory:
    """Lightweight memory system using claude-mem database."""

    def __init__(self, user_id: str = "leo"):
        self.user_id = user_id
        self.claude_mem_db = Path.home() / ".claude-mem" / "claude-mem.db"
        self.ccb_memory_db = Path.home() / ".ccb" / "ccb_memory.db"
        self.ccb_memory_db.parent.mkdir(parents=True, exist_ok=True)

        # Initialize CCB memory database
        self._init_ccb_db()

    def _init_ccb_db(self):
        """Initialize CCB memory database."""
        conn = sqlite3.connect(self.ccb_memory_db)
        cursor = conn.cursor()

        # Create conversations table
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

        # Create learnings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT
            )
        ''')

        # Create FTS5 index for full-text search
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
                question, answer, provider,
                content='conversations',
                content_rowid='id'
            )
        ''')

        conn.commit()
        conn.close()

    def record_conversation(
        self,
        provider: str,
        question: str,
        answer: str,
        metadata: Optional[Dict[str, Any]] = None,
        tokens: int = 0
    ) -> int:
        """Record a conversation."""
        conn = sqlite3.connect(self.ccb_memory_db)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO conversations (timestamp, provider, question, answer, metadata, tokens)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            provider,
            question,
            answer,
            json.dumps(metadata or {}),
            tokens
        ))

        rowid = cursor.lastrowid

        # Update FTS index
        cursor.execute('''
            INSERT INTO conversations_fts(rowid, question, answer, provider)
            VALUES (?, ?, ?, ?)
        ''', (rowid, question, answer, provider))

        conn.commit()
        conn.close()

        return rowid

    def search_conversations(
        self,
        query: str,
        limit: int = 5,
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search conversations using full-text search."""
        conn = sqlite3.connect(self.ccb_memory_db)
        cursor = conn.cursor()

        if provider:
            cursor.execute('''
                SELECT c.id, c.timestamp, c.provider, c.question, c.answer, c.metadata
                FROM conversations c
                JOIN conversations_fts fts ON c.id = fts.rowid
                WHERE conversations_fts MATCH ? AND c.provider = ?
                ORDER BY c.timestamp DESC
                LIMIT ?
            ''', (query, provider, limit))
        else:
            cursor.execute('''
                SELECT c.id, c.timestamp, c.provider, c.question, c.answer, c.metadata
                FROM conversations c
                JOIN conversations_fts fts ON c.id = fts.rowid
                WHERE conversations_fts MATCH ?
                ORDER BY c.timestamp DESC
                LIMIT ?
            ''', (query, limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "timestamp": row[1],
                "provider": row[2],
                "question": row[3],
                "answer": row[4][:300],  # Truncate for display
                "metadata": json.loads(row[5]) if row[5] else {}
            })

        conn.close()
        return results

    def get_recent_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversations."""
        conn = sqlite3.connect(self.ccb_memory_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, timestamp, provider, question, answer, metadata
            FROM conversations
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "timestamp": row[1],
                "provider": row[2],
                "question": row[3],
                "answer": row[4][:300],
                "metadata": json.loads(row[5]) if row[5] else {}
            })

        conn.close()
        return results

    def get_task_context(self, task_keywords: List[str]) -> Dict[str, Any]:
        """Get comprehensive context for a task."""
        # Search for relevant conversations
        query = " OR ".join(task_keywords)
        conversations = self.search_conversations(query, limit=3)

        # Get provider recommendations from registry
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from registry import CCBRegistry

        registry = CCBRegistry()
        providers = registry.find_provider_for_task(task_keywords)

        # Get relevant skills
        registry_data = registry.load_cache() or registry.generate_registry()
        relevant_skills = []
        for skill in registry_data.get("skills", []):
            for keyword in task_keywords:
                if keyword.lower() in skill.get("description", "").lower():
                    relevant_skills.append({
                        "name": skill["name"],
                        "description": skill["description"][:100]
                    })
                    break

        return {
            "conversations": conversations,
            "recommended_providers": providers[:3],
            "relevant_skills": relevant_skills[:5],
            "mcp_servers": registry_data.get("mcp_servers", []),
            "query": query
        }

    def format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """Format context into human-readable prompt addition."""
        lines = []

        # Add relevant conversations
        if context.get("conversations"):
            lines.append("## 💭 相关记忆 (历史对话)")
            for i, conv in enumerate(context["conversations"], 1):
                lines.append(f"\n{i}. [{conv['provider']}] {conv['timestamp'][:10]}")
                lines.append(f"   Q: {conv['question'][:100]}")
                lines.append(f"   A: {conv['answer'][:200]}")

        # Add provider recommendations
        if context.get("recommended_providers"):
            lines.append("\n## 🤖 推荐使用的 AI")
            for provider in context["recommended_providers"]:
                lines.append(f"- {provider['provider']}: {provider['command']} (匹配度: {provider['score']}★)")

        # Add relevant skills
        if context.get("relevant_skills"):
            lines.append("\n## 🛠️ 可用的 Skills")
            for skill in context["relevant_skills"]:
                lines.append(f"- {skill['name']}: {skill['description']}")

        # Add MCP servers
        if context.get("mcp_servers"):
            lines.append("\n## 🔌 运行中的 MCP Servers")
            for mcp in context["mcp_servers"][:3]:
                lines.append(f"- {mcp['name']} (PID: {mcp['pid']})")

        return "\n".join(lines)

    def record_learning(self, learning: str, category: str = "general"):
        """Record a learning or insight."""
        conn = sqlite3.connect(self.ccb_memory_db)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO learnings (timestamp, category, content, metadata)
            VALUES (?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            category,
            learning,
            json.dumps({})
        ))

        conn.commit()
        conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        conn = sqlite3.connect(self.ccb_memory_db)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM conversations')
        total_conversations = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM learnings')
        total_learnings = cursor.fetchone()[0]

        cursor.execute('SELECT SUM(tokens) FROM conversations')
        total_tokens = cursor.fetchone()[0] or 0

        cursor.execute('SELECT provider, COUNT(*) as count FROM conversations GROUP BY provider ORDER BY count DESC')
        provider_stats = cursor.fetchall()

        conn.close()

        return {
            "total_conversations": total_conversations,
            "total_learnings": total_learnings,
            "total_tokens": total_tokens,
            "provider_stats": [{"provider": p[0], "count": p[1]} for p in provider_stats]
        }


def main():
    """CLI for memory operations."""
    import sys

    memory = CCBLightMemory()

    if len(sys.argv) < 2:
        _emit("Usage: memory_lite.py [record|search|context|stats|recent] [args...]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "record":
        if len(sys.argv) < 5:
            _emit("Usage: memory_lite.py record <provider> <question> <answer>")
            sys.exit(1)

        provider = sys.argv[2]
        question = sys.argv[3]
        answer = " ".join(sys.argv[4:])

        record_id = memory.record_conversation(provider, question, answer)
        _emit(f"✓ Recorded conversation #{record_id}")

    elif command == "search":
        if len(sys.argv) < 3:
            _emit("Usage: memory_lite.py search <query>")
            sys.exit(1)

        query = " ".join(sys.argv[2:])
        results = memory.search_conversations(query)

        if results:
            _emit(f"Found {len(results)} results for: {query}\n")
            for i, result in enumerate(results, 1):
                _emit(f"{i}. [{result['provider']}] {result['timestamp'][:19]}")
                _emit(f"   Q: {result['question'][:100]}")
                _emit(f"   A: {result['answer'][:200]}")
                _emit()
        else:
            _emit("No results found.")

    elif command == "context":
        if len(sys.argv) < 3:
            _emit("Usage: memory_lite.py context <task_keywords...>")
            sys.exit(1)

        keywords = sys.argv[2:]
        context = memory.get_task_context(keywords)

        _emit(memory.format_context_for_prompt(context))

    elif command == "recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        conversations = memory.get_recent_conversations(limit)

        _emit(f"Recent {len(conversations)} conversations:\n")
        for conv in conversations:
            _emit(f"[{conv['provider']}] {conv['timestamp'][:19]}")
            _emit(f"Q: {conv['question'][:80]}")
            _emit(f"A: {conv['answer'][:150]}")
            _emit()

    elif command == "stats":
        stats = memory.get_stats()
        _emit("CCB Memory Statistics")
        _emit("=" * 40)
        _emit(f"Total conversations: {stats['total_conversations']}")
        _emit(f"Total learnings: {stats['total_learnings']}")
        _emit(f"Total tokens: {stats['total_tokens']:,}")
        _emit("\nProvider Usage:")
        for p in stats['provider_stats']:
            _emit(f"  {p['provider']}: {p['count']} conversations")

    else:
        _emit(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
