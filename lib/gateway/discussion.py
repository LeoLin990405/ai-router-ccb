"""Discussion Executor for CCB Gateway.

Provides multi-round AI discussion orchestration across multiple providers.
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List, TYPE_CHECKING, Callable

from .models import (
    DiscussionStatus,
    DiscussionSession,
    DiscussionMessage,
    DiscussionConfig,
    MessageType,
    WebSocketEvent,
)
from .state_store import StateStore
from .discussion_exporters import DiscussionExporter, ObsidianExporter
from .discussion_prompts import DiscussionPromptBuilder
from .discussion_executor_rounds import (
    run_full_discussion_impl,
    _execute_round_impl,
    _execute_provider_impl,
    _generate_summary_impl,
)
from .discussion_executor_continue import (
    continue_discussion_impl,
    run_continued_discussion_impl,
)

if TYPE_CHECKING:
    from .backends.base_backend import BaseBackend


class DiscussionExecutor:
    """
    Orchestrates multi-round AI discussions.

    Usage:
        executor = DiscussionExecutor(store, backends, config)
        session = await executor.start_discussion(topic, providers)
        await executor.run_full_discussion(session.id)
    """

    def __init__(
        self,
        store: StateStore,
        backends: Dict[str, "BaseBackend"],
        gateway_config: Any = None,
        ws_broadcast: Optional[Callable] = None,
    ):
        """
        Initialize the discussion executor.

        Args:
            store: State store for persistence
            backends: Dict of provider name -> backend instance
            gateway_config: Gateway configuration
            ws_broadcast: Optional WebSocket broadcast function
        """
        self.store = store
        self.backends = backends
        self.gateway_config = gateway_config
        self.ws_broadcast = ws_broadcast
        self.prompt_builder = DiscussionPromptBuilder()

    async def start_discussion(
        self,
        topic: str,
        providers: List[str],
        config: Optional[DiscussionConfig] = None,
    ) -> DiscussionSession:
        """
        Start a new discussion session.

        Args:
            topic: The discussion topic
            providers: List of provider names to participate
            config: Optional discussion configuration

        Returns:
            Created DiscussionSession
        """
        # Filter to available providers
        available_providers = [p for p in providers if p in self.backends]

        if len(available_providers) < (config or DiscussionConfig()).min_providers:
            raise ValueError(
                f"Not enough available providers. Need at least "
                f"{(config or DiscussionConfig()).min_providers}, "
                f"got {len(available_providers)}"
            )

        # Create session
        session = DiscussionSession.create(
            topic=topic,
            providers=available_providers,
            config=config,
        )

        # Persist
        self.store.create_discussion_session(session)

        # Broadcast event
        await self._broadcast(WebSocketEvent(
            type="discussion_started",
            data={
                "session_id": session.id,
                "topic": topic,
                "providers": available_providers,
            },
        ))

        return session

    async def cancel_discussion(self, session_id: str) -> bool:
        """Cancel an ongoing discussion."""
        session = self.store.get_discussion_session(session_id)
        if not session:
            return False

        if session.status in (DiscussionStatus.COMPLETED, DiscussionStatus.CANCELLED):
            return False

        self.store.update_discussion_session(
            session_id,
            status=DiscussionStatus.CANCELLED,
        )

        await self._broadcast(WebSocketEvent(
            type="discussion_cancelled",
            data={"session_id": session_id},
        ))

        return True

    async def _broadcast(self, event: WebSocketEvent) -> None:
        """Broadcast WebSocket event if handler is available."""
        if self.ws_broadcast:
            try:
                await self.ws_broadcast(event)
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
                pass  # Don't let broadcast errors affect discussion

    def get_provider_groups(self) -> Dict[str, List[str]]:
        """Get available provider groups for discussions."""
        # Default groups
        groups = {
            "all": list(self.backends.keys()),
            "fast": [],
            "coding": [],
        }

        # Categorize providers
        fast_providers = {"kimi", "qwen", "iflow"}
        coding_providers = {"codex", "gemini", "qwen", "kimi", "opencode"}

        for provider in self.backends.keys():
            if provider.lower() in fast_providers:
                groups["fast"].append(provider)
            if provider.lower() in coding_providers:
                groups["coding"].append(provider)

        return groups

    def resolve_provider_group(self, spec: str) -> List[str]:
        """Resolve a provider specification to a list of providers."""
        if spec.startswith("@"):
            group_name = spec[1:]
            groups = self.get_provider_groups()
            return groups.get(group_name, [])
        return [spec] if spec in self.backends else []

    async def run_full_discussion(self, session_id: str) -> DiscussionSession:
        return await run_full_discussion_impl(self, session_id)

    async def _execute_round(
        self,
        session: DiscussionSession,
        round_number: int,
        message_type: MessageType,
    ) -> List[DiscussionMessage]:
        return await _execute_round_impl(self, session, round_number, message_type)

    async def _execute_provider(
        self,
        session: DiscussionSession,
        message: DiscussionMessage,
        prompt: str,
        provider: str,
    ) -> DiscussionMessage:
        return await _execute_provider_impl(self, session, message, prompt, provider)

    async def _generate_summary(self, session: DiscussionSession) -> str:
        return await _generate_summary_impl(self, session)

    async def continue_discussion(
        self,
        parent_session_id: str,
        follow_up_topic: str,
        additional_context: Optional[str] = None,
        max_rounds: int = 2,
        providers: Optional[List[str]] = None,
    ) -> DiscussionSession:
        return await continue_discussion_impl(
            self,
            parent_session_id,
            follow_up_topic,
            additional_context=additional_context,
            max_rounds=max_rounds,
            providers=providers,
        )

    async def run_continued_discussion(self, session_id: str) -> DiscussionSession:
        return await run_continued_discussion_impl(self, session_id)
