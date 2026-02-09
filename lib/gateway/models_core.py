"""Dataclass-based core gateway models."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
import time
import uuid

from .models_enums import (
    RequestStatus,
    BackendType,
    ProviderStatus,
    DiscussionStatus,
    MessageType,
)


@dataclass
class GatewayRequest:
    """Represents a request to the gateway."""
    id: str
    provider: str
    message: str
    status: RequestStatus
    created_at: float
    updated_at: float
    priority: int = 50
    timeout_s: float = 300.0
    metadata: Optional[Dict[str, Any]] = None
    # Routing info
    backend_type: Optional[BackendType] = None
    routed_at: Optional[float] = None
    # Response tracking
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    @classmethod
    def create(
        cls,
        provider: str,
        message: str,
        priority: int = 50,
        timeout_s: float = 300.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "GatewayRequest":
        """Create a new request with generated ID."""
        now = time.time()
        return cls(
            id=str(uuid.uuid4()),
            provider=provider,
            message=message,
            status=RequestStatus.QUEUED,
            created_at=now,
            updated_at=now,
            priority=priority,
            timeout_s=timeout_s,
            metadata=metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["status"] = self.status.value
        if self.backend_type:
            d["backend_type"] = self.backend_type.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GatewayRequest":
        """Create from dictionary."""
        data = data.copy()
        data["status"] = RequestStatus(data["status"])
        if data.get("backend_type"):
            data["backend_type"] = BackendType(data["backend_type"])
        return cls(**data)

@dataclass
class GatewayResponse:
    """Represents a response from a provider."""
    request_id: str
    status: RequestStatus
    response: Optional[str] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    latency_ms: Optional[float] = None
    tokens_used: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    # Extended output fields for monitoring
    thinking: Optional[str] = None  # Extracted thinking/reasoning chain
    raw_output: Optional[str] = None  # Full raw CLI output

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["status"] = self.status.value
        return d

@dataclass
class ProviderInfo:
    """Information about a provider."""
    name: str
    backend_type: BackendType
    status: ProviderStatus = ProviderStatus.UNKNOWN
    queue_depth: int = 0
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
    last_check: Optional[float] = None
    error: Optional[str] = None
    # Configuration
    enabled: bool = True
    priority: int = 50
    rate_limit_rpm: Optional[int] = None
    timeout_s: float = 300.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        d["backend_type"] = self.backend_type.value
        d["status"] = self.status.value
        return d

@dataclass
class GatewayStats:
    """Gateway statistics."""
    uptime_s: float
    total_requests: int
    active_requests: int
    completed_requests: int
    failed_requests: int
    avg_latency_ms: float
    providers: List[ProviderInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        d["providers"] = [p.to_dict() for p in self.providers]
        return d

@dataclass
class WebSocketEvent:
    """Event for WebSocket broadcast."""
    type: str  # "request_update", "provider_status", "gateway_stats"
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
        }

@dataclass
class StreamChunk:
    """A chunk of streamed response."""
    request_id: str
    content: str
    chunk_index: int
    is_final: bool = False
    tokens_used: Optional[int] = None
    provider: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "is_final": self.is_final,
            "tokens_used": self.tokens_used,
            "provider": self.provider,
            "metadata": self.metadata,
        }

@dataclass
class CacheEntry:
    """A cached response entry."""
    cache_key: str
    provider: str
    message_hash: str
    response: str
    tokens_used: Optional[int]
    created_at: float
    expires_at: float
    hit_count: int = 0
    last_hit_at: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cache_key": self.cache_key,
            "provider": self.provider,
            "message_hash": self.message_hash,
            "response": self.response,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "hit_count": self.hit_count,
            "last_hit_at": self.last_hit_at,
            "metadata": self.metadata,
        }

@dataclass
class DiscussionConfig:
    """Configuration for a discussion session."""
    max_rounds: int = 3
    round_timeout_s: float = 120.0  # Timeout per round
    provider_timeout_s: float = 120.0  # Timeout per provider
    min_providers: int = 2  # Minimum providers required
    summary_provider: Optional[str] = None  # Provider for final summary (None = Claude)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_rounds": self.max_rounds,
            "round_timeout_s": self.round_timeout_s,
            "provider_timeout_s": self.provider_timeout_s,
            "min_providers": self.min_providers,
            "summary_provider": self.summary_provider,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiscussionConfig":
        """Create from dictionary."""
        return cls(**data)

@dataclass
class DiscussionMessage:
    """A message in a discussion session."""
    id: str
    session_id: str
    round_number: int
    provider: str
    message_type: MessageType
    content: Optional[str] = None
    references_messages: Optional[List[str]] = None  # IDs of messages this references
    latency_ms: Optional[float] = None
    status: str = "pending"  # pending, completed, failed, timeout
    created_at: float = field(default_factory=time.time)
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        session_id: str,
        round_number: int,
        provider: str,
        message_type: MessageType,
        references: Optional[List[str]] = None,
    ) -> "DiscussionMessage":
        """Create a new discussion message."""
        return cls(
            id=str(uuid.uuid4()),
            session_id=session_id,
            round_number=round_number,
            provider=provider,
            message_type=message_type,
            references_messages=references,
            created_at=time.time(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "round_number": self.round_number,
            "provider": self.provider,
            "message_type": self.message_type.value,
            "content": self.content,
            "references_messages": self.references_messages,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiscussionMessage":
        """Create from dictionary."""
        data = data.copy()
        data["message_type"] = MessageType(data["message_type"])
        return cls(**data)

@dataclass
class DiscussionSession:
    """A multi-AI discussion session."""
    id: str
    topic: str
    status: DiscussionStatus
    current_round: int
    providers: List[str]
    config: DiscussionConfig
    created_at: float
    updated_at: float
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        topic: str,
        providers: List[str],
        config: Optional[DiscussionConfig] = None,
    ) -> "DiscussionSession":
        """Create a new discussion session."""
        now = time.time()
        return cls(
            id=str(uuid.uuid4()),
            topic=topic,
            status=DiscussionStatus.PENDING,
            current_round=0,
            providers=providers,
            config=config or DiscussionConfig(),
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "topic": self.topic,
            "status": self.status.value,
            "current_round": self.current_round,
            "providers": self.providers,
            "config": self.config.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "summary": self.summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiscussionSession":
        """Create from dictionary."""
        data = data.copy()
        data["status"] = DiscussionStatus(data["status"])
        data["config"] = DiscussionConfig.from_dict(data["config"])
        return cls(**data)

