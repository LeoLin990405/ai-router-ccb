"""Continuation flows extracted from ``DiscussionExecutor``."""

from __future__ import annotations

from typing import Optional, List

from .models import DiscussionStatus, DiscussionSession, DiscussionConfig, WebSocketEvent


async def continue_discussion_impl(
    self,
    parent_session_id: str,
    follow_up_topic: str,
    additional_context: Optional[str] = None,
    max_rounds: int = 2,
    providers: Optional[List[str]] = None,
) -> DiscussionSession:
    """
    Continue from a completed discussion with a follow-up topic.

    Args:
        parent_session_id: The completed discussion to continue from
        follow_up_topic: The new topic/question to explore
        additional_context: Optional additional context
        max_rounds: Number of rounds for the continuation (default 2)
        providers: Optional list of providers (defaults to parent's providers)

    Returns:
        New DiscussionSession linked to the parent
    """
    # Get parent session
    parent = self.store.get_discussion_session(parent_session_id)
    if not parent:
        raise ValueError(f"Parent discussion not found: {parent_session_id}")

    if parent.status != DiscussionStatus.COMPLETED:
        raise ValueError(f"Can only continue from completed discussions. Current status: {parent.status.value}")

    # Get parent messages for context
    parent_messages = self.store.get_discussion_messages(parent_session_id)

    # Build context from parent discussion
    context_parts = [
        f"This is a continuation of a previous discussion.",
        f"\n## Previous Discussion Topic\n{parent.topic}",
    ]

    if parent.summary:
        context_parts.append(f"\n## Previous Discussion Summary\n{parent.summary}")

    # Include key messages from parent
    round_3_messages = [m for m in parent_messages if m.round_number == 3 and m.content]
    if round_3_messages:
        context_parts.append("\n## Final Proposals from Previous Discussion")
        for msg in round_3_messages[:3]:  # Limit to avoid too much context
            context_parts.append(f"\n### {msg.provider}:\n{msg.content[:500]}...")

    if additional_context:
        context_parts.append(f"\n## Additional Context\n{additional_context}")

    # Build new topic with context
    full_topic = f"""## Follow-up Discussion

**New Topic**: {follow_up_topic}

{''.join(context_parts)}

---

Please provide your analysis and recommendations for this follow-up topic, building upon the previous discussion."""

    # Use parent's providers if not specified
    use_providers = providers or parent.providers

    # Create config for continuation (shorter by default)
    config = DiscussionConfig(
        max_rounds=min(max_rounds, 3),
        round_timeout_s=parent.config.round_timeout_s,
        provider_timeout_s=parent.config.provider_timeout_s,
    )

    # Create new session
    session = DiscussionSession.create(
        topic=follow_up_topic,  # Store the short topic
        providers=use_providers,
        config=config,
    )

    # Store with parent reference in metadata
    session.metadata = {
        "parent_session_id": parent_session_id,
        "parent_topic": parent.topic,
        "full_context_topic": full_topic,
    }

    # Persist
    self.store.create_discussion_session(session)

    # Update session to include parent reference
    with self.store._get_connection() as conn:
        conn.execute(
            "UPDATE discussion_sessions SET parent_session_id = ? WHERE id = ?",
            (parent_session_id, session.id)
        )

    # Broadcast event
    await self._broadcast(WebSocketEvent(
        type="discussion_continued",
        data={
            "session_id": session.id,
            "parent_session_id": parent_session_id,
            "topic": follow_up_topic,
            "providers": use_providers,
        },
    ))

    return session
async def run_continued_discussion_impl(self, session_id: str) -> DiscussionSession:
    """
    Run a continued discussion using the full context topic.

    Similar to run_full_discussion but uses the full_context_topic from metadata.
    """
    session = self.store.get_discussion_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    # Get the full context topic if available
    if session.metadata and "full_context_topic" in session.metadata:
        # Temporarily update the topic for prompts
        original_topic = session.topic
        session.topic = session.metadata["full_context_topic"]

    try:
        # Run the discussion with context
        result = await self.run_full_discussion(session_id)

        # Restore original topic for display
        if session.metadata and "full_context_topic" in session.metadata:
            self.store.update_discussion_session(
                session_id,
                metadata={**session.metadata, "display_topic": original_topic},
            )

        return result
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
        raise

