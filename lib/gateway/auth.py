"""
Authentication Middleware for CCB Gateway.

Provides API key authentication and management.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Awaitable

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@dataclass
class AuthConfig:
    """Configuration for API authentication."""
    enabled: bool = False  # Disabled by default for backward compatibility
    header_name: str = "X-API-Key"
    allow_localhost: bool = True  # Allow unauthenticated access from localhost
    # Paths that don't require authentication
    public_paths: List[str] = field(default_factory=lambda: [
        "/api/health",
        "/metrics",
        "/",
        "/docs",
        "/openapi.json",
    ])


@dataclass
class APIKey:
    """Represents an API key."""
    key_id: str
    key_hash: str  # SHA-256 hash of the actual key
    name: str
    created_at: float
    last_used_at: Optional[float] = None
    rate_limit_rpm: Optional[int] = None  # Per-key rate limit override
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excludes key_hash for security)."""
        return {
            "key_id": self.key_id,
            "name": self.name,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "rate_limit_rpm": self.rate_limit_rpm,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (key_id, raw_key)
    """
    # Generate a secure random key
    raw_key = secrets.token_urlsafe(32)
    # Generate a short ID for reference
    key_id = secrets.token_hex(8)
    return key_id, raw_key


def hash_api_key(raw_key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class APIKeyStore:
    """
    Manages API keys with SQLite persistence.
    """

    def __init__(self, store):
        """
        Initialize the API key store.

        Args:
            store: StateStore instance for persistence
        """
        self.store = store
        self._init_table()

    def _init_table(self) -> None:
        """Initialize the API keys table."""
        with self.store._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    key_hash TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_used_at REAL,
                    rate_limit_rpm INTEGER,
                    enabled INTEGER DEFAULT 1,
                    metadata TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)")

    def create_key(
        self,
        name: str,
        rate_limit_rpm: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> tuple[APIKey, str]:
        """
        Create a new API key.

        Args:
            name: Human-readable name for the key
            rate_limit_rpm: Optional per-key rate limit
            metadata: Optional metadata

        Returns:
            Tuple of (APIKey, raw_key) - raw_key is only returned once!
        """
        import json

        key_id, raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key)
        now = time.time()

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            created_at=now,
            rate_limit_rpm=rate_limit_rpm,
            metadata=metadata,
        )

        with self.store._get_connection() as conn:
            conn.execute("""
                INSERT INTO api_keys (
                    key_id, key_hash, name, created_at, last_used_at,
                    rate_limit_rpm, enabled, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                api_key.key_id,
                api_key.key_hash,
                api_key.name,
                api_key.created_at,
                api_key.last_used_at,
                api_key.rate_limit_rpm,
                1 if api_key.enabled else 0,
                json.dumps(api_key.metadata) if api_key.metadata else None,
            ))

        return api_key, raw_key

    def validate_key(self, raw_key: str) -> Optional[APIKey]:
        """
        Validate an API key and return the associated APIKey if valid.

        Args:
            raw_key: The raw API key to validate

        Returns:
            APIKey if valid and enabled, None otherwise
        """
        import json

        key_hash = hash_api_key(raw_key)

        with self.store._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM api_keys WHERE key_hash = ? AND enabled = 1",
                (key_hash,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            # Update last_used_at
            now = time.time()
            conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE key_id = ?",
                (now, row["key_id"])
            )

            return APIKey(
                key_id=row["key_id"],
                key_hash=row["key_hash"],
                name=row["name"],
                created_at=row["created_at"],
                last_used_at=now,
                rate_limit_rpm=row["rate_limit_rpm"],
                enabled=bool(row["enabled"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )

    def get_key(self, key_id: str) -> Optional[APIKey]:
        """Get an API key by ID."""
        import json

        with self.store._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM api_keys WHERE key_id = ?",
                (key_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return APIKey(
                key_id=row["key_id"],
                key_hash=row["key_hash"],
                name=row["name"],
                created_at=row["created_at"],
                last_used_at=row["last_used_at"],
                rate_limit_rpm=row["rate_limit_rpm"],
                enabled=bool(row["enabled"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )

    def list_keys(self) -> List[APIKey]:
        """List all API keys."""
        import json

        with self.store._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM api_keys ORDER BY created_at DESC"
            )
            keys = []
            for row in cursor.fetchall():
                keys.append(APIKey(
                    key_id=row["key_id"],
                    key_hash=row["key_hash"],
                    name=row["name"],
                    created_at=row["created_at"],
                    last_used_at=row["last_used_at"],
                    rate_limit_rpm=row["rate_limit_rpm"],
                    enabled=bool(row["enabled"]),
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                ))
            return keys

    def delete_key(self, key_id: str) -> bool:
        """Delete an API key."""
        with self.store._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM api_keys WHERE key_id = ?",
                (key_id,)
            )
            return cursor.rowcount > 0

    def disable_key(self, key_id: str) -> bool:
        """Disable an API key."""
        with self.store._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE api_keys SET enabled = 0 WHERE key_id = ?",
                (key_id,)
            )
            return cursor.rowcount > 0

    def enable_key(self, key_id: str) -> bool:
        """Enable an API key."""
        with self.store._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE api_keys SET enabled = 1 WHERE key_id = ?",
                (key_id,)
            )
            return cursor.rowcount > 0


class AuthMiddleware:
    """
    FastAPI middleware for API key authentication.
    """

    def __init__(
        self,
        config: AuthConfig,
        key_store: APIKeyStore,
    ):
        """
        Initialize the auth middleware.

        Args:
            config: Authentication configuration
            key_store: API key store instance
        """
        self.config = config
        self.key_store = key_store

    def _is_localhost(self, request: "Request") -> bool:
        """Check if request is from localhost."""
        client_host = request.client.host if request.client else None
        return client_host in ("127.0.0.1", "localhost", "::1")

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        return any(path.startswith(p) for p in self.config.public_paths)

    async def __call__(
        self,
        request: "Request",
        call_next: Callable[["Request"], Awaitable[Any]],
    ):
        """Process the request."""
        if not HAS_FASTAPI:
            return await call_next(request)

        # Skip auth if disabled
        if not self.config.enabled:
            return await call_next(request)

        # Skip auth for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Skip auth for localhost if allowed
        if self.config.allow_localhost and self._is_localhost(request):
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get(self.config.header_name)

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Missing API key",
                    "detail": f"Provide API key in {self.config.header_name} header",
                },
            )

        # Validate API key
        key_info = self.key_store.validate_key(api_key)

        if not key_info:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Invalid API key",
                    "detail": "The provided API key is invalid or disabled",
                },
            )

        # Store key info in request state for downstream use
        request.state.api_key = key_info

        return await call_next(request)
