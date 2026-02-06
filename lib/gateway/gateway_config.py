"""
Gateway Configuration Management.

Handles loading and managing gateway configuration from YAML files
and environment variables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List
import os
import yaml

from .models import BackendType


# Default fallback chains for providers
DEFAULT_FALLBACK_CHAINS: Dict[str, List[str]] = {
    "gemini": ["deepseek", "qwen"],
    "deepseek": ["qwen", "kimi"],
    "codex": ["opencode", "gemini"],
    "opencode": ["codex", "gemini"],
    "kimi": ["qwen", "deepseek"],
    "qwen": ["kimi", "deepseek"],
    "iflow": ["deepseek", "gemini"],
    "qoder": ["codex", "gemini"],
    "claude": ["codex", "gemini"],
}

# Default provider groups for parallel queries
DEFAULT_PROVIDER_GROUPS: Dict[str, List[str]] = {
    "all": ["gemini", "deepseek", "codex", "opencode", "kimi", "qwen", "iflow", "qoder", "claude"],
    "fast": ["deepseek", "kimi"],
    "reasoning": ["deepseek", "gemini", "claude"],
    "coding": ["codex", "opencode", "gemini", "qoder", "claude"],
    "chinese": ["deepseek", "kimi", "qwen"],
}


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""
    name: str
    backend_type: BackendType
    enabled: bool = True
    priority: int = 50
    timeout_s: float = 300.0
    rate_limit_rpm: Optional[int] = None
    # Backend-specific config
    api_base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    cli_command: Optional[str] = None
    cli_args: List[str] = field(default_factory=list)
    fifo_path: Optional[str] = None
    terminal_pane_id: Optional[str] = None
    # Model config
    model: Optional[str] = None
    max_tokens: int = 4096
    # Streaming support
    supports_streaming: bool = False


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    enabled: bool = True
    max_retries: int = 3
    base_delay_s: float = 1.0
    max_delay_s: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    # Fallback configuration
    fallback_enabled: bool = True
    fallback_chains: Dict[str, List[str]] = field(default_factory=lambda: DEFAULT_FALLBACK_CHAINS.copy())

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt."""
        import random
        delay = self.base_delay_s * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay_s)
        if self.jitter:
            delay = delay * (0.5 + random.random())
        return delay

    def get_fallbacks(self, provider: str) -> List[str]:
        """Get fallback providers for a given provider."""
        return self.fallback_chains.get(provider, [])


@dataclass
class CacheConfig:
    """Configuration for response caching."""
    enabled: bool = True
    default_ttl_s: float = 3600.0  # 1 hour default
    max_entries: int = 10000
    # TTL by provider
    provider_ttl_s: Dict[str, float] = field(default_factory=lambda: {
        "gemini": 3600.0,
        "deepseek": 1800.0,
        "codex": 1800.0,
    })
    # Don't cache responses shorter than this
    min_response_length: int = 10
    # Patterns that should not be cached
    no_cache_patterns: List[str] = field(default_factory=lambda: [
        "current time", "current date", "today", "now",
        "latest", "recent", "weather", "stock price", "random",
    ])

    def get_ttl(self, provider: str) -> float:
        """Get TTL for a provider."""
        return self.provider_ttl_s.get(provider, self.default_ttl_s)

    def should_cache_message(self, message: str) -> bool:
        """Check if a message should be cached based on patterns."""
        message_lower = message.lower()
        return not any(p in message_lower for p in self.no_cache_patterns)


@dataclass
class StreamConfig:
    """Configuration for streaming."""
    enabled: bool = True
    chunk_size: int = 50
    chunk_delay_ms: float = 50.0
    heartbeat_interval_s: float = 15.0
    timeout_s: float = 300.0


@dataclass
class ParallelConfig:
    """Configuration for parallel execution."""
    enabled: bool = True
    default_strategy: str = "first_success"  # first_success, fastest, all, consensus
    timeout_s: float = 60.0
    min_responses: int = 1
    max_concurrent: int = 5
    # Provider groups
    provider_groups: Dict[str, List[str]] = field(default_factory=lambda: DEFAULT_PROVIDER_GROUPS.copy())

    def get_provider_group(self, group_name: str) -> List[str]:
        """Get providers in a named group."""
        name = group_name.lstrip("@")
        return self.provider_groups.get(name, [])


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
class RateLimitConfig:
    """Configuration for rate limiting."""
    enabled: bool = True
    requests_per_minute: int = 60  # Default: 60 RPM
    burst_size: int = 10  # Allow burst of up to 10 requests
    by_api_key: bool = True  # Rate limit per API key
    by_ip: bool = True  # Rate limit per IP address
    # Separate limits for different endpoint types
    endpoint_limits: Dict[str, int] = field(default_factory=lambda: {
        "/api/ask": 30,  # More restrictive for AI requests
        "/api/ask/stream": 30,
        "/api/admin": 10,  # Very restrictive for admin endpoints
    })


@dataclass
class MetricsConfig:
    """Configuration for Prometheus metrics."""
    enabled: bool = True
    endpoint: str = "/metrics"
    use_prometheus_client: bool = True  # Use prometheus_client if available


@dataclass
class GatewayConfig:
    """Gateway configuration."""
    # Server settings
    host: str = "127.0.0.1"
    port: int = 8765
    # Database
    db_path: Optional[str] = None
    # Timeouts
    default_timeout_s: float = 300.0
    request_ttl_hours: int = 24
    # Queue settings
    max_queue_size: int = 1000
    max_concurrent_requests: int = 10
    # Provider configs
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    # Default provider for auto-routing
    default_provider: str = "deepseek"
    # WebSocket settings
    ws_enabled: bool = True
    ws_heartbeat_s: float = 30.0
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    # Advanced features
    retry: RetryConfig = field(default_factory=RetryConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    streaming: StreamConfig = field(default_factory=StreamConfig)
    parallel: ParallelConfig = field(default_factory=ParallelConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    # Health check configuration
    health_check: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "GatewayConfig":
        """
        Load configuration from file and environment.

        Priority: Environment > Config file > Defaults
        """
        config = cls()

        # Try to load from file
        if config_path:
            config._load_from_file(config_path)
        else:
            # Try default locations
            default_paths = [
                Path.home() / ".ccb_config" / "gateway.yaml",
                Path.home() / ".config" / "ccb" / "gateway.yaml",
                Path("/etc/ccb/gateway.yaml"),
            ]
            for path in default_paths:
                if path.exists():
                    config._load_from_file(str(path))
                    break

        # Override with environment variables
        config._load_from_env()

        # Initialize default providers if none configured
        if not config.providers:
            config._init_default_providers()

        return config

    def _load_from_file(self, path: str) -> None:
        """Load configuration from YAML file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # Server settings
            server = data.get("server", {})
            self.host = server.get("host", self.host)
            self.port = server.get("port", self.port)

            # Database
            self.db_path = data.get("database", {}).get("path", self.db_path)

            # Timeouts
            timeouts = data.get("timeouts", {})
            self.default_timeout_s = timeouts.get("default_s", self.default_timeout_s)
            self.request_ttl_hours = timeouts.get("request_ttl_hours", self.request_ttl_hours)

            # Queue
            queue = data.get("queue", {})
            self.max_queue_size = queue.get("max_size", self.max_queue_size)
            self.max_concurrent_requests = queue.get("max_concurrent", self.max_concurrent_requests)

            # Default provider
            self.default_provider = data.get("default_provider", self.default_provider)

            # WebSocket
            ws = data.get("websocket", {})
            self.ws_enabled = ws.get("enabled", self.ws_enabled)
            self.ws_heartbeat_s = ws.get("heartbeat_s", self.ws_heartbeat_s)

            # Logging
            logging = data.get("logging", {})
            self.log_level = logging.get("level", self.log_level)
            self.log_file = logging.get("file", self.log_file)

            # Health check configuration
            self.health_check = data.get("health_check", {})

            # Providers
            for name, pconfig in data.get("providers", {}).items():
                self.providers[name] = self._parse_provider_config(name, pconfig)

        except Exception as e:
            print(f"Warning: Failed to load config from {path}: {e}")

    def _parse_provider_config(self, name: str, data: Dict[str, Any]) -> ProviderConfig:
        """Parse a provider configuration."""
        backend_str = data.get("backend_type", "cli_exec")
        try:
            backend_type = BackendType(backend_str)
        except ValueError:
            backend_type = BackendType.CLI_EXEC

        return ProviderConfig(
            name=name,
            backend_type=backend_type,
            enabled=data.get("enabled", True),
            priority=data.get("priority", 50),
            timeout_s=data.get("timeout_s", self.default_timeout_s),
            rate_limit_rpm=data.get("rate_limit_rpm"),
            api_base_url=data.get("api_base_url"),
            api_key_env=data.get("api_key_env"),
            cli_command=data.get("cli_command"),
            cli_args=data.get("cli_args", []),
            fifo_path=data.get("fifo_path"),
            terminal_pane_id=data.get("terminal_pane_id"),
            model=data.get("model"),
            max_tokens=data.get("max_tokens", 4096),
        )

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # Server
        if os.environ.get("CCB_GATEWAY_HOST"):
            self.host = os.environ["CCB_GATEWAY_HOST"]
        if os.environ.get("CCB_GATEWAY_PORT"):
            try:
                self.port = int(os.environ["CCB_GATEWAY_PORT"])
            except ValueError:
                pass

        # Database
        if os.environ.get("CCB_GATEWAY_DB"):
            self.db_path = os.environ["CCB_GATEWAY_DB"]

        # Default provider
        if os.environ.get("CCB_DEFAULT_PROVIDER"):
            self.default_provider = os.environ["CCB_DEFAULT_PROVIDER"]

        # Timeouts
        if os.environ.get("CCB_GATEWAY_TIMEOUT"):
            try:
                self.default_timeout_s = float(os.environ["CCB_GATEWAY_TIMEOUT"])
            except ValueError:
                pass

        # Log level
        if os.environ.get("CCB_GATEWAY_LOG_LEVEL"):
            self.log_level = os.environ["CCB_GATEWAY_LOG_LEVEL"]

    def _init_default_providers(self) -> None:
        """Initialize default provider configurations."""
        # DeepSeek (CLI) - use '-q' for quick/non-interactive mode
        self.providers["deepseek"] = ProviderConfig(
            name="deepseek",
            backend_type=BackendType.CLI_EXEC,
            cli_command="deepseek",
            cli_args=["-q"],
            timeout_s=120.0,  # Longer timeout for reasoning
        )

        # Codex (CLI) - use 'exec --json' for non-interactive mode with JSON output
        self.providers["codex"] = ProviderConfig(
            name="codex",
            backend_type=BackendType.CLI_EXEC,
            cli_command="codex",
            cli_args=["exec", "--json"],
            timeout_s=300.0,
        )

        # Gemini (CLI) - requires TTY, use terminal backend or WezTerm execution
        # Note: Gemini CLI uses OAuth authentication, not API key
        # The -p flag requires the prompt to follow immediately, so we use positional args
        self.providers["gemini"] = ProviderConfig(
            name="gemini",
            backend_type=BackendType.CLI_EXEC,
            cli_command="gemini",
            cli_args=["-o", "json"],  # Output format, prompt will be added as positional arg
            timeout_s=300.0,
        )

        # OpenCode (CLI) - use 'run --format json' for non-interactive mode
        self.providers["opencode"] = ProviderConfig(
            name="opencode",
            backend_type=BackendType.CLI_EXEC,
            cli_command="opencode",
            cli_args=["run", "--format", "json", "-m", "opencode/minimax-m2.1-free"],
            timeout_s=120.0,
        )

        # iFlow (CLI) - use '-p' for non-interactive prompt mode
        self.providers["iflow"] = ProviderConfig(
            name="iflow",
            backend_type=BackendType.CLI_EXEC,
            cli_command="iflow",
            cli_args=["-p"],
            timeout_s=300.0,
        )

        # Kimi (CLI) - use '--quiet' for non-interactive mode
        self.providers["kimi"] = ProviderConfig(
            name="kimi",
            backend_type=BackendType.CLI_EXEC,
            cli_command="kimi",
            cli_args=["--quiet", "-p"],
            timeout_s=300.0,
        )

        # Qwen (CLI)
        self.providers["qwen"] = ProviderConfig(
            name="qwen",
            backend_type=BackendType.CLI_EXEC,
            cli_command="qwen",
            timeout_s=300.0,
        )

        # Qoder (CLI) - use 'qodercli' command with -p flag for non-interactive mode
        self.providers["qoder"] = ProviderConfig(
            name="qoder",
            backend_type=BackendType.CLI_EXEC,
            cli_command="qodercli",
            cli_args=["-p"],
            timeout_s=120.0,
        )

        # Claude (CLI) - use 'claude' command with -p flag for prompt mode
        self.providers["claude"] = ProviderConfig(
            name="claude",
            backend_type=BackendType.CLI_EXEC,
            cli_command="claude",
            cli_args=["-p"],
            timeout_s=300.0,
        )

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Get provider configuration by name."""
        return self.providers.get(name)

    def get_enabled_providers(self) -> List[ProviderConfig]:
        """Get list of enabled providers."""
        return [p for p in self.providers.values() if p.enabled]

    def get_db_path(self) -> Path:
        """Get the database path, creating directory if needed."""
        if self.db_path:
            path = Path(self.db_path)
        else:
            path = Path.home() / ".ccb_config" / "gateway.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "server": {
                "host": self.host,
                "port": self.port,
            },
            "database": {
                "path": str(self.get_db_path()),
            },
            "timeouts": {
                "default_s": self.default_timeout_s,
                "request_ttl_hours": self.request_ttl_hours,
            },
            "queue": {
                "max_size": self.max_queue_size,
                "max_concurrent": self.max_concurrent_requests,
            },
            "default_provider": self.default_provider,
            "websocket": {
                "enabled": self.ws_enabled,
                "heartbeat_s": self.ws_heartbeat_s,
            },
            "logging": {
                "level": self.log_level,
                "file": self.log_file,
            },
            "providers": {
                name: {
                    "backend_type": p.backend_type.value,
                    "enabled": p.enabled,
                    "priority": p.priority,
                    "timeout_s": p.timeout_s,
                }
                for name, p in self.providers.items()
            },
        }
