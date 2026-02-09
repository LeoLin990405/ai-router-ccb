"""Pydantic request/response models for gateway HTTP API."""
from __future__ import annotations

from typing import Optional, Dict, Any, List

from .models_base import BaseModel, Field


class AskRequest(BaseModel):
    """Request body for /api/ask endpoint."""
    message: str = Field(..., description="The message to send to the provider")
    provider: Optional[str] = Field(None, description="Provider name, @group, or auto-routed if not specified")
    timeout_s: float = Field(300.0, description="Request timeout in seconds")
    priority: int = Field(50, description="Request priority (higher = more urgent)")
    cache_bypass: bool = Field(False, description="Bypass cache for this request")
    aggregation_strategy: Optional[str] = Field(None, description="Strategy for parallel queries: first_success, fastest, all, consensus")
    agent: Optional[str] = Field(None, description="Agent role assigned by orchestrator (e.g., sisyphus, oracle, reviewer)")

class AskResponse(BaseModel):
    """Response body for /api/ask endpoint."""
    request_id: str
    provider: str
    status: str
    cached: bool = False
    parallel: bool = False
    agent: Optional[str] = None

class ReplyResponse(BaseModel):
    """Response body for /api/reply endpoint."""
    request_id: str
    status: str
    response: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    cached: bool = False
    retry_info: Optional[Dict[str, Any]] = None
    thinking: Optional[str] = None
    raw_output: Optional[str] = None

class StatusResponse(BaseModel):
    """Response body for /api/status endpoint."""
    gateway: Dict[str, Any]
    providers: List[Dict[str, Any]]

class CacheStatsResponse(BaseModel):
    """Response body for /api/cache/stats endpoint."""
    hits: int
    misses: int
    hit_rate: float
    total_entries: int
    expired_entries: int
    total_tokens_saved: int
    size_bytes: Optional[int] = None
    valid_entries: Optional[int] = None
    valid_size_bytes: Optional[int] = None
    oldest_entry: Optional[float] = None
    newest_entry: Optional[float] = None
    next_expiration: Optional[float] = None
    avg_ttl_remaining_s: Optional[float] = None

class BatchAskRequest(BaseModel):
    """Request body for batch ask operation."""
    requests: List[AskRequest] = Field(..., min_length=1, max_length=50, description="List of requests to submit")

class BatchCancelRequest(BaseModel):
    """Request body for batch cancel operation."""
    request_ids: List[str] = Field(..., min_length=1, max_length=100, description="List of request IDs to cancel")

class BatchStatusRequest(BaseModel):
    """Request body for batch status query."""
    request_ids: List[str] = Field(..., min_length=1, max_length=100, description="List of request IDs to query")

class BatchReplyRequest(BaseModel):
    """Request body for batch reply query."""
    request_ids: List[str] = Field(..., min_length=1, max_length=100, description="List of request IDs to fetch replies")

class ParallelResponse(BaseModel):
    """Response body for parallel query results."""
    request_id: str
    strategy: str
    selected_provider: Optional[str] = None
    selected_response: Optional[str] = None
    all_responses: Dict[str, Any] = {}
    latency_ms: float = 0.0
    success: bool = False
    error: Optional[str] = None

class CreateAPIKeyRequest(BaseModel):
    """Request body for creating an API key."""
    name: str = Field(..., description="Human-readable name for the key")
    rate_limit_rpm: Optional[int] = Field(None, description="Per-key rate limit override")

class CreateAPIKeyResponse(BaseModel):
    """Response body for creating an API key."""
    key_id: str
    api_key: str
    name: str
    created_at: float

class APIKeyInfo(BaseModel):
    """API key information (without the actual key)."""
    key_id: str
    name: str
    created_at: float
    last_used_at: Optional[float] = None
    rate_limit_rpm: Optional[int] = None
    enabled: bool = True

class StartDiscussionRequest(BaseModel):
    """Request body for starting a discussion."""
    topic: str = Field(..., description="The discussion topic")
    providers: Optional[List[str]] = Field(None, description="List of providers or None for default")
    provider_group: Optional[str] = Field(None, description="Provider group like @all, @fast, @coding")
    max_rounds: int = Field(3, description="Maximum discussion rounds (1-3)")
    round_timeout_s: float = Field(120.0, description="Timeout per round in seconds")
    provider_timeout_s: float = Field(120.0, description="Timeout per provider in seconds")
    run_async: bool = Field(True, description="Run discussion asynchronously")

class DiscussionResponse(BaseModel):
    """Response body for discussion operations."""
    session_id: str
    topic: str
    status: str
    current_round: int
    providers: List[str]
    created_at: float
    summary: Optional[str] = None

class DiscussionMessageResponse(BaseModel):
    """Response body for a discussion message."""
    id: str
    session_id: str
    round_number: int
    provider: str
    message_type: str
    content: Optional[str] = None
    status: str
    latency_ms: Optional[float] = None
    created_at: float

class CreateTemplateRequest(BaseModel):
    """Request body for creating a discussion template."""
    name: str = Field(..., description="Unique template name")
    topic_template: str = Field(..., description="Template with placeholders like {subject}")
    description: Optional[str] = Field(None, description="Template description")
    default_providers: Optional[List[str]] = Field(None, description="Default providers list")
    default_config: Optional[Dict[str, Any]] = Field(None, description="Default discussion config")
    category: Optional[str] = Field(None, description="Template category")

class UseTemplateRequest(BaseModel):
    """Request body for using a template to start a discussion."""
    variables: Dict[str, str] = Field(default_factory=dict, description="Variables to fill in template")
    providers: Optional[List[str]] = Field(None, description="Override default providers")
    config: Optional[Dict[str, Any]] = Field(None, description="Override default config")
    run_async: bool = Field(True, description="Run discussion asynchronously")

class ContinueDiscussionRequest(BaseModel):
    """Request body for continuing a discussion."""
    follow_up_topic: str = Field(..., description="The follow-up topic to discuss")
    additional_context: Optional[str] = Field(None, description="Additional context")
    max_rounds: int = Field(2, description="Number of rounds for continuation")

class ExportObsidianRequest(BaseModel):
    """Request body for exporting to Obsidian."""
    vault_path: str = Field(..., description="Path to Obsidian vault")
    folder: str = Field("CCB Discussions", description="Subfolder within vault")

class SaveDiscussionMemoryRequest(BaseModel):
    """Request body for saving discussion to memory."""
    summary_override: Optional[str] = Field(None, description="Override auto-generated summary")
    tags: Optional[List[str]] = Field(None, description="Tags for the memory")

class CreateObservationRequest(BaseModel):
    """Request body for creating an observation."""
    content: str = Field(..., min_length=1, description="Observation content")
    category: str = Field("note", description="Category: insight, preference, fact, note")
    tags: Optional[List[str]] = Field(None, description="Tags for the observation")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score")

class UpdateObservationRequest(BaseModel):
    """Request body for updating an observation."""
    content: Optional[str] = Field(None, description="New content")
    category: Optional[str] = Field(None, description="New category")
    tags: Optional[List[str]] = Field(None, description="New tags")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="New confidence")

class UpdateConfigRequest(BaseModel):
    """Request body for updating memory configuration."""
    enabled: Optional[bool] = Field(None, description="Enable/disable memory system")
    auto_inject: Optional[bool] = Field(None, description="Auto-inject memories")
    max_injected_memories: Optional[int] = Field(None, ge=0, le=50, description="Max memories to inject")
    injection_strategy: Optional[str] = Field(None, description="Injection strategy")
    skills_auto_discover: Optional[bool] = Field(None, description="Auto-discover skills")
    skills_max_recommendations: Optional[int] = Field(None, ge=0, le=10, description="Max skill recommendations")

class SkillFeedbackRequest(BaseModel):
    """Request body for skill feedback."""
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    helpful: bool = Field(True, description="Was the skill helpful?")
    task_description: Optional[str] = Field(None, description="Task description")
    comment: Optional[str] = Field(None, description="Optional comment")

class CCParallelTestRequest(BaseModel):
    """Request body for CC Switch parallel test."""
    message: str = Field(..., description="Test message to send to providers")
    providers: Optional[List[str]] = Field(None, description="List of provider names (default: all active)")
    timeout_s: float = Field(60.0, description="Timeout in seconds", ge=1.0, le=300.0)

