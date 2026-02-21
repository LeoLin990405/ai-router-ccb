"""
State Store for CCB Gateway.

SQLite-backed persistent storage for requests, responses, and provider status.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterator

from lib.common.paths import default_gateway_db_path

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

from .state_store_requests import (
    create_request_impl,
    get_request_impl,
    update_request_status_impl,
    list_requests_impl,
    get_pending_requests_impl,
    cancel_request_impl,
    cleanup_old_requests_impl,
    _row_to_request_impl,
    save_response_impl,
    get_response_impl,
)
from .state_store_providers import (
    update_provider_status_impl,
    get_provider_status_impl,
    list_provider_status_impl,
    _row_to_provider_info_impl,
    record_metric_impl,
    get_provider_metrics_impl,
    cleanup_old_metrics_impl,
    get_stats_impl,
)
from .state_store_discussions import (
    create_discussion_session_impl,
    get_discussion_session_impl,
    update_discussion_session_impl,
    list_discussion_sessions_impl,
    delete_discussion_session_impl,
    _row_to_discussion_session_impl,
    create_discussion_message_impl,
    update_discussion_message_impl,
    get_discussion_messages_impl,
    _row_to_discussion_message_impl,
    cleanup_old_discussions_impl,
    create_discussion_template_impl,
    get_discussion_template_impl,
    get_discussion_template_by_name_impl,
    list_discussion_templates_impl,
    update_discussion_template_impl,
    delete_discussion_template_impl,
    increment_template_usage_impl,
    _row_to_template_impl,
)
from .state_store_costs import (
    record_token_cost_impl,
    get_cost_summary_impl,
    get_cost_by_provider_impl,
    get_cost_by_day_impl,
    cleanup_old_costs_impl,
    get_latest_results_impl,
    get_result_by_id_impl,
)


class StateStore:
    """
    SQLite-backed state store for the gateway.

    Stores:
    - Requests and their status
    - Responses from providers
    - Provider health/status information
    - Request metrics for analytics
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the state store.

        Args:
            db_path: Path to SQLite database. Defaults to data/hivemind.db
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = default_gateway_db_path()

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            # Requests table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    priority INTEGER NOT NULL DEFAULT 50,
                    timeout_s REAL NOT NULL DEFAULT 300.0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    backend_type TEXT,
                    routed_at REAL,
                    started_at REAL,
                    completed_at REAL,
                    metadata TEXT
                )
            """)

            # Responses table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    request_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    response TEXT,
                    error TEXT,
                    provider TEXT,
                    latency_ms REAL,
                    tokens_used INTEGER,
                    created_at REAL NOT NULL,
                    metadata TEXT,
                    thinking TEXT,
                    raw_output TEXT,
                    FOREIGN KEY (request_id) REFERENCES requests(id)
                )
            """)

            # Add thinking and raw_output columns if they don't exist (migration)
            try:
                conn.execute("ALTER TABLE responses ADD COLUMN thinking TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            try:
                conn.execute("ALTER TABLE responses ADD COLUMN raw_output TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Provider status table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS provider_status (
                    name TEXT PRIMARY KEY,
                    backend_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'unknown',
                    queue_depth INTEGER DEFAULT 0,
                    avg_latency_ms REAL DEFAULT 0.0,
                    success_rate REAL DEFAULT 1.0,
                    last_check REAL,
                    error TEXT,
                    enabled INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 50,
                    rate_limit_rpm INTEGER,
                    timeout_s REAL DEFAULT 300.0,
                    updated_at REAL NOT NULL
                )
            """)

            # Metrics table for analytics
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    request_id TEXT,
                    event_type TEXT NOT NULL,
                    latency_ms REAL,
                    success INTEGER,
                    error TEXT,
                    timestamp REAL NOT NULL
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_provider ON requests(provider)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_created ON requests(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_priority ON requests(priority DESC, created_at ASC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_request ON responses(request_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_provider ON metrics(provider)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)")

            # Initialize discussion tables
            self._init_discussion_tables(conn)

            # Initialize cost tracking table
            self._init_cost_tracking_table(conn)

    def _init_cost_tracking_table(self, conn: sqlite3.Connection) -> None:
        """Initialize token cost tracking table."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                request_id TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cost_usd REAL,
                model TEXT,
                timestamp REAL NOT NULL
            )
        """)

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_costs_provider ON token_costs(provider)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_costs_timestamp ON token_costs(timestamp)")

    def _init_discussion_tables(self, conn: sqlite3.Connection) -> None:
        """Initialize discussion-related tables."""
        # Discussion sessions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS discussion_sessions (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                current_round INTEGER DEFAULT 0,
                providers TEXT NOT NULL,
                config TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                summary TEXT,
                metadata TEXT,
                parent_session_id TEXT
            )
        """)

        # Add parent_session_id column if it doesn't exist (migration)
        try:
            conn.execute("ALTER TABLE discussion_sessions ADD COLUMN parent_session_id TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Discussion messages table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS discussion_messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                round_number INTEGER NOT NULL,
                provider TEXT NOT NULL,
                message_type TEXT NOT NULL,
                content TEXT,
                references_messages TEXT,
                latency_ms REAL,
                status TEXT DEFAULT 'pending',
                created_at REAL NOT NULL,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES discussion_sessions(id)
            )
        """)

        # Discussion templates table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS discussion_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                topic_template TEXT NOT NULL,
                default_providers TEXT,
                default_config TEXT,
                category TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                usage_count INTEGER DEFAULT 0,
                is_builtin INTEGER DEFAULT 0
            )
        """)

        # Create indexes for discussion tables
        conn.execute("CREATE INDEX IF NOT EXISTS idx_discussion_sessions_status ON discussion_sessions(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_discussion_sessions_created ON discussion_sessions(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_discussion_messages_session ON discussion_messages(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_discussion_messages_round ON discussion_messages(session_id, round_number)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_discussion_templates_category ON discussion_templates(category)")

        # Initialize built-in templates
        self._init_builtin_templates(conn)

    def _init_builtin_templates(self, conn: sqlite3.Connection) -> None:
        """Initialize built-in discussion templates."""
        builtin_templates = [
            {
                "id": "arch-review",
                "name": "Architecture Review",
                "description": "Review and discuss system architecture decisions",
                "topic_template": "Review the architecture for: {subject}\n\nContext:\n{context}\n\nFocus areas:\n- Scalability\n- Maintainability\n- Security\n- Performance",
                "default_providers": '["kimi", "qwen", "iflow"]',
                "default_config": '{"max_rounds": 3, "provider_timeout_s": 120}',
                "category": "engineering",
            },
            {
                "id": "code-review",
                "name": "Code Review",
                "description": "Collaborative code review with multiple AI perspectives",
                "topic_template": "Review the following code:\n\n```{language}\n{code}\n```\n\nFocus on:\n- Code quality and best practices\n- Potential bugs or issues\n- Performance considerations\n- Security vulnerabilities",
                "default_providers": '["kimi", "qwen", "iflow"]',
                "default_config": '{"max_rounds": 2, "provider_timeout_s": 90}',
                "category": "engineering",
            },
            {
                "id": "api-design",
                "name": "API Design",
                "description": "Design and review API endpoints and contracts",
                "topic_template": "Design an API for: {subject}\n\nRequirements:\n{requirements}\n\nConsider:\n- RESTful principles\n- Error handling\n- Versioning strategy\n- Authentication/Authorization",
                "default_providers": '["kimi", "qwen", "iflow"]',
                "default_config": '{"max_rounds": 3, "provider_timeout_s": 120}',
                "category": "engineering",
            },
            {
                "id": "bug-analysis",
                "name": "Bug Analysis",
                "description": "Analyze and diagnose bugs collaboratively",
                "topic_template": "Analyze this bug:\n\nSymptoms:\n{symptoms}\n\nReproduction steps:\n{steps}\n\nRelevant code:\n```\n{code}\n```\n\nIdentify:\n- Root cause\n- Impact assessment\n- Recommended fix\n- Prevention strategies",
                "default_providers": '["kimi", "qwen", "iflow"]',
                "default_config": '{"max_rounds": 2, "provider_timeout_s": 90}',
                "category": "debugging",
            },
            {
                "id": "perf-optimization",
                "name": "Performance Optimization",
                "description": "Discuss and plan performance improvements",
                "topic_template": "Optimize performance for: {subject}\n\nCurrent metrics:\n{metrics}\n\nBottlenecks identified:\n{bottlenecks}\n\nPropose:\n- Quick wins\n- Long-term improvements\n- Trade-offs to consider",
                "default_providers": '["kimi", "qwen", "iflow"]',
                "default_config": '{"max_rounds": 3, "provider_timeout_s": 120}',
                "category": "engineering",
            },
        ]

        now = time.time()
        for template in builtin_templates:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO discussion_templates (
                        id, name, description, topic_template, default_providers,
                        default_config, category, created_at, updated_at, is_builtin
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    template["id"],
                    template["name"],
                    template["description"],
                    template["topic_template"],
                    template["default_providers"],
                    template["default_config"],
                    template["category"],
                    now,
                    now,
                ))
            except sqlite3.IntegrityError:
                pass  # Template already exists

    # ==================== Request Operations ====================

    def create_request(self, *args, **kwargs):
        return create_request_impl(self, *args, **kwargs)
    def get_request(self, *args, **kwargs):
        return get_request_impl(self, *args, **kwargs)
    def update_request_status(self, *args, **kwargs):
        return update_request_status_impl(self, *args, **kwargs)
    def list_requests(self, *args, **kwargs):
        return list_requests_impl(self, *args, **kwargs)
    def get_pending_requests(self, *args, **kwargs):
        return get_pending_requests_impl(self, *args, **kwargs)
    def cancel_request(self, *args, **kwargs):
        return cancel_request_impl(self, *args, **kwargs)
    def cleanup_old_requests(self, *args, **kwargs):
        return cleanup_old_requests_impl(self, *args, **kwargs)
    def _row_to_request(self, *args, **kwargs):
        return _row_to_request_impl(self, *args, **kwargs)
    def save_response(self, *args, **kwargs):
        return save_response_impl(self, *args, **kwargs)
    def get_response(self, *args, **kwargs):
        return get_response_impl(self, *args, **kwargs)
    def update_provider_status(self, *args, **kwargs):
        return update_provider_status_impl(self, *args, **kwargs)
    def get_provider_status(self, *args, **kwargs):
        return get_provider_status_impl(self, *args, **kwargs)
    def list_provider_status(self, *args, **kwargs):
        return list_provider_status_impl(self, *args, **kwargs)
    def _row_to_provider_info(self, *args, **kwargs):
        return _row_to_provider_info_impl(self, *args, **kwargs)
    def record_metric(self, *args, **kwargs):
        return record_metric_impl(self, *args, **kwargs)
    def get_provider_metrics(self, *args, **kwargs):
        return get_provider_metrics_impl(self, *args, **kwargs)
    def cleanup_old_metrics(self, *args, **kwargs):
        return cleanup_old_metrics_impl(self, *args, **kwargs)
    def get_stats(self, *args, **kwargs):
        return get_stats_impl(self, *args, **kwargs)
    def create_discussion_session(self, *args, **kwargs):
        return create_discussion_session_impl(self, *args, **kwargs)
    def get_discussion_session(self, *args, **kwargs):
        return get_discussion_session_impl(self, *args, **kwargs)
    def update_discussion_session(self, *args, **kwargs):
        return update_discussion_session_impl(self, *args, **kwargs)
    def list_discussion_sessions(self, *args, **kwargs):
        return list_discussion_sessions_impl(self, *args, **kwargs)
    def delete_discussion_session(self, *args, **kwargs):
        return delete_discussion_session_impl(self, *args, **kwargs)
    def _row_to_discussion_session(self, *args, **kwargs):
        return _row_to_discussion_session_impl(self, *args, **kwargs)
    def create_discussion_message(self, *args, **kwargs):
        return create_discussion_message_impl(self, *args, **kwargs)
    def update_discussion_message(self, *args, **kwargs):
        return update_discussion_message_impl(self, *args, **kwargs)
    def get_discussion_messages(self, *args, **kwargs):
        return get_discussion_messages_impl(self, *args, **kwargs)
    def _row_to_discussion_message(self, *args, **kwargs):
        return _row_to_discussion_message_impl(self, *args, **kwargs)
    def cleanup_old_discussions(self, *args, **kwargs):
        return cleanup_old_discussions_impl(self, *args, **kwargs)
    def create_discussion_template(self, *args, **kwargs):
        return create_discussion_template_impl(self, *args, **kwargs)
    def get_discussion_template(self, *args, **kwargs):
        return get_discussion_template_impl(self, *args, **kwargs)
    def get_discussion_template_by_name(self, *args, **kwargs):
        return get_discussion_template_by_name_impl(self, *args, **kwargs)
    def list_discussion_templates(self, *args, **kwargs):
        return list_discussion_templates_impl(self, *args, **kwargs)
    def update_discussion_template(self, *args, **kwargs):
        return update_discussion_template_impl(self, *args, **kwargs)
    def delete_discussion_template(self, *args, **kwargs):
        return delete_discussion_template_impl(self, *args, **kwargs)
    def increment_template_usage(self, *args, **kwargs):
        return increment_template_usage_impl(self, *args, **kwargs)
    def _row_to_template(self, *args, **kwargs):
        return _row_to_template_impl(self, *args, **kwargs)
    def record_token_cost(self, *args, **kwargs):
        return record_token_cost_impl(self, *args, **kwargs)
    def get_cost_summary(self, *args, **kwargs):
        return get_cost_summary_impl(self, *args, **kwargs)
    def get_cost_by_provider(self, *args, **kwargs):
        return get_cost_by_provider_impl(self, *args, **kwargs)
    def get_cost_by_day(self, *args, **kwargs):
        return get_cost_by_day_impl(self, *args, **kwargs)
    def cleanup_old_costs(self, *args, **kwargs):
        return cleanup_old_costs_impl(self, *args, **kwargs)
    def get_latest_results(self, *args, **kwargs):
        return get_latest_results_impl(self, *args, **kwargs)
    def get_result_by_id(self, *args, **kwargs):
        return get_result_by_id_impl(self, *args, **kwargs)
