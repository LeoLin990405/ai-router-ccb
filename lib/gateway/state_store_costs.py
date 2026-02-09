"""StateStore operation helpers extracted from ``StateStore``."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Optional, List, Dict, Any

from .models import (
    RequestStatus,
    GatewayRequest,
    GatewayResponse,
    ProviderInfo,
    ProviderStatus,
    BackendType,
    DiscussionStatus,
    DiscussionSession,
    DiscussionMessage,
    DiscussionConfig,
    MessageType,
)


def record_token_cost_impl(
    self,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    request_id: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Record token usage and calculate cost."""
    # Calculate cost
    pricing = self.PROVIDER_PRICING.get(provider.lower(), {"input": 0, "output": 0})
    cost_usd = (
        (input_tokens * pricing["input"] / 1_000_000) +
        (output_tokens * pricing["output"] / 1_000_000)
    )

    with self._get_connection() as conn:
        conn.execute("""
            INSERT INTO token_costs (
                provider, request_id, input_tokens, output_tokens,
                cost_usd, model, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            provider,
            request_id,
            input_tokens,
            output_tokens,
            cost_usd,
            model,
            time.time(),
        ))

def get_cost_summary_impl(self, days: int = 30) -> Dict[str, Any]:
    """Get cost summary for the specified period."""
    cutoff = time.time() - (days * 86400)

    with self._get_connection() as conn:
        # Total costs
        cursor = conn.execute("""
            SELECT
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output,
                SUM(cost_usd) as total_cost,
                COUNT(*) as total_requests
            FROM token_costs
            WHERE timestamp > ?
        """, (cutoff,))
        row = cursor.fetchone()

        # Today's costs
        today_start = time.time() - (time.time() % 86400)
        cursor = conn.execute("""
            SELECT SUM(cost_usd) as today_cost
            FROM token_costs
            WHERE timestamp > ?
        """, (today_start,))
        today_row = cursor.fetchone()

        # This week's costs
        week_start = time.time() - (7 * 86400)
        cursor = conn.execute("""
            SELECT SUM(cost_usd) as week_cost
            FROM token_costs
            WHERE timestamp > ?
        """, (week_start,))
        week_row = cursor.fetchone()

        return {
            "period_days": days,
            "total_input_tokens": row["total_input"] or 0,
            "total_output_tokens": row["total_output"] or 0,
            "total_cost_usd": row["total_cost"] or 0.0,
            "total_requests": row["total_requests"] or 0,
            "today_cost_usd": today_row["today_cost"] or 0.0,
            "week_cost_usd": week_row["week_cost"] or 0.0,
        }

def get_cost_by_provider_impl(self, days: int = 30) -> List[Dict[str, Any]]:
    """Get cost breakdown by provider."""
    cutoff = time.time() - (days * 86400)

    with self._get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                provider,
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output,
                SUM(cost_usd) as total_cost,
                COUNT(*) as request_count
            FROM token_costs
            WHERE timestamp > ?
            GROUP BY provider
            ORDER BY total_cost DESC
        """, (cutoff,))

        return [
            {
                "provider": row["provider"],
                "total_input_tokens": row["total_input"] or 0,
                "total_output_tokens": row["total_output"] or 0,
                "total_cost_usd": row["total_cost"] or 0.0,
                "request_count": row["request_count"] or 0,
            }
            for row in cursor.fetchall()
        ]

def get_cost_by_day_impl(self, days: int = 7) -> List[Dict[str, Any]]:
    """Get daily cost breakdown."""
    cutoff = time.time() - (days * 86400)

    with self._get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                DATE(timestamp, 'unixepoch', 'localtime') as date,
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output,
                SUM(cost_usd) as total_cost,
                COUNT(*) as request_count
            FROM token_costs
            WHERE timestamp > ?
            GROUP BY DATE(timestamp, 'unixepoch', 'localtime')
            ORDER BY date DESC
        """, (cutoff,))

        return [
            {
                "date": row["date"],
                "total_input_tokens": row["total_input"] or 0,
                "total_output_tokens": row["total_output"] or 0,
                "total_cost_usd": row["total_cost"] or 0.0,
                "request_count": row["request_count"] or 0,
            }
            for row in cursor.fetchall()
        ]

def cleanup_old_costs_impl(self, max_age_days: int = 90) -> int:
    """Remove cost records older than specified age."""
    cutoff = time.time() - (max_age_days * 86400)
    with self._get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM token_costs WHERE timestamp < ?",
            (cutoff,)
        )
        return cursor.rowcount

def get_latest_results_impl(
    self,
    provider: Optional[str] = None,
    limit: int = 10,
    include_discussions: bool = True,
) -> List[Dict[str, Any]]:
    """
    Get latest results from all sources (requests + discussions) for Claude to read.

    Returns unified format:
    {
        "id": str,
        "type": "request" | "discussion",
        "provider": str,
        "query": str,  # original message/topic
        "response": str,
        "status": str,
        "created_at": float,
        "latency_ms": float,
        "metadata": dict
    }
    """
    results = []

    with self._get_connection() as conn:
        # Get recent request responses
        query = """
            SELECT r.id, r.provider, r.message, r.status, r.created_at,
                   resp.response, resp.latency_ms, resp.metadata, resp.thinking
            FROM requests r
            LEFT JOIN responses resp ON r.id = resp.request_id
            WHERE r.status IN ('completed', 'failed')
        """
        params: List[Any] = []

        if provider:
            query += " AND r.provider = ?"
            params.append(provider)

        query += " ORDER BY r.created_at DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "type": "request",
                "provider": row["provider"],
                "query": row["message"][:200] + "..." if len(row["message"] or "") > 200 else row["message"],
                "response": row["response"],
                "status": row["status"],
                "created_at": row["created_at"],
                "latency_ms": row["latency_ms"],
                "thinking": row["thinking"] if "thinking" in row.keys() else None,
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
            })

        # Get recent discussion summaries
        if include_discussions:
            disc_query = """
                SELECT id, topic, status, providers, summary, created_at, updated_at
                FROM discussion_sessions
                WHERE status IN ('completed', 'failed')
                ORDER BY created_at DESC
                LIMIT ?
            """
            cursor = conn.execute(disc_query, (limit,))
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "type": "discussion",
                    "provider": json.loads(row["providers"]) if row["providers"] else [],
                    "query": row["topic"],
                    "response": row["summary"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "latency_ms": (row["updated_at"] - row["created_at"]) * 1000 if row["updated_at"] else None,
                    "metadata": {"providers": json.loads(row["providers"]) if row["providers"] else []},
                })

    # Sort by created_at descending
    results.sort(key=lambda x: x["created_at"], reverse=True)
    return results[:limit]

def get_result_by_id_impl(self, result_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific result by ID (request or discussion)."""
    # Try request first
    with self._get_connection() as conn:
        cursor = conn.execute("""
            SELECT r.id, r.provider, r.message, r.status, r.created_at,
                   resp.response, resp.error, resp.latency_ms, resp.metadata,
                   resp.thinking, resp.raw_output
            FROM requests r
            LEFT JOIN responses resp ON r.id = resp.request_id
            WHERE r.id = ?
        """, (result_id,))
        row = cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "type": "request",
                "provider": row["provider"],
                "query": row["message"],
                "response": row["response"],
                "error": row["error"],
                "status": row["status"],
                "created_at": row["created_at"],
                "latency_ms": row["latency_ms"],
                "thinking": row["thinking"] if "thinking" in row.keys() else None,
                "raw_output": row["raw_output"] if "raw_output" in row.keys() else None,
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
            }

        # Try discussion
        cursor = conn.execute("""
            SELECT id, topic, status, providers, summary, created_at, updated_at, metadata
            FROM discussion_sessions
            WHERE id = ?
        """, (result_id,))
        row = cursor.fetchone()
        if row:
            # Also get all messages
            messages = self.get_discussion_messages(result_id)
            return {
                "id": row["id"],
                "type": "discussion",
                "provider": json.loads(row["providers"]) if row["providers"] else [],
                "query": row["topic"],
                "response": row["summary"],
                "status": row["status"],
                "created_at": row["created_at"],
                "latency_ms": (row["updated_at"] - row["created_at"]) * 1000 if row["updated_at"] else None,
                "messages": [m.to_dict() for m in messages],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
            }

    return None

