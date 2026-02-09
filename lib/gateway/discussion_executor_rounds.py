"""Heavy discussion execution steps extracted from ``DiscussionExecutor``."""

from __future__ import annotations

import asyncio
import time
from typing import List

from .models import (
    DiscussionStatus,
    DiscussionSession,
    DiscussionMessage,
    MessageType,
    GatewayRequest,
    WebSocketEvent,
)


async def run_full_discussion_impl(self, session_id: str) -> DiscussionSession:
    """
    Run a complete discussion through all rounds.

    Args:
        session_id: The session ID to run

    Returns:
        Updated DiscussionSession with summary
    """
    session = self.store.get_discussion_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    try:
        # Round 1: Proposals
        await self._execute_round(session, 1, MessageType.PROPOSAL)

        # Round 2: Reviews
        await self._execute_round(session, 2, MessageType.REVIEW)

        # Round 3: Revisions
        await self._execute_round(session, 3, MessageType.REVISION)

        # Generate summary
        await self._generate_summary(session)

        # Mark completed
        self.store.update_discussion_session(
            session_id,
            status=DiscussionStatus.COMPLETED,
        )

        await self._broadcast(WebSocketEvent(
            type="discussion_completed",
            data={
                "session_id": session_id,
                "status": "completed",
            },
        ))

    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        self.store.update_discussion_session(
            session_id,
            status=DiscussionStatus.FAILED,
            metadata={"error": str(e)},
        )

        await self._broadcast(WebSocketEvent(
            type="discussion_failed",
            data={
                "session_id": session_id,
                "error": str(e),
            },
        ))

        raise

    return self.store.get_discussion_session(session_id)

async def _execute_round_impl(
    self,
    session: DiscussionSession,
    round_number: int,
    message_type: MessageType,
) -> List[DiscussionMessage]:
    """Execute a single round of discussion."""
    # Update session status
    status_map = {
        1: DiscussionStatus.ROUND_1,
        2: DiscussionStatus.ROUND_2,
        3: DiscussionStatus.ROUND_3,
    }
    self.store.update_discussion_session(
        session.id,
        status=status_map.get(round_number, DiscussionStatus.ROUND_1),
        current_round=round_number,
    )

    await self._broadcast(WebSocketEvent(
        type="discussion_round_started",
        data={
            "session_id": session.id,
            "round": round_number,
            "message_type": message_type.value,
        },
    ))

    # Get previous messages for context
    all_messages = self.store.get_discussion_messages(session.id)
    round_1_messages = [m for m in all_messages if m.round_number == 1]
    round_2_messages = [m for m in all_messages if m.round_number == 2]

    # Create tasks for all providers
    tasks = []
    for provider in session.providers:
        # Build prompt based on round
        if round_number == 1:
            prompt = self.prompt_builder.build_proposal_prompt(
                session.topic, provider
            )
        elif round_number == 2:
            # Get proposals from other providers
            other_proposals = [m for m in round_1_messages if m.provider != provider]
            prompt = self.prompt_builder.build_review_prompt(
                session.topic, provider, other_proposals
            )
        else:  # round 3
            # Get original proposal and feedback
            original = next(
                (m for m in round_1_messages if m.provider == provider),
                None
            )
            if not original:
                continue
            feedback = [m for m in round_2_messages if m.provider != provider]
            prompt = self.prompt_builder.build_revision_prompt(
                session.topic, provider, original, feedback
            )

        # Create message placeholder
        message = DiscussionMessage.create(
            session_id=session.id,
            round_number=round_number,
            provider=provider,
            message_type=message_type,
        )
        self.store.create_discussion_message(message)

        # Create execution task
        tasks.append(self._execute_provider(
            session, message, prompt, provider
        ))

    # Execute all providers in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect successful messages
    messages = []
    for result in results:
        if isinstance(result, DiscussionMessage):
            messages.append(result)

    await self._broadcast(WebSocketEvent(
        type="discussion_round_completed",
        data={
            "session_id": session.id,
            "round": round_number,
            "successful_providers": [m.provider for m in messages],
        },
    ))

    return messages

async def _execute_provider_impl(
    self,
    session: DiscussionSession,
    message: DiscussionMessage,
    prompt: str,
    provider: str,
) -> DiscussionMessage:
    """Execute a single provider request."""
    backend = self.backends.get(provider)
    if not backend:
        self.store.update_discussion_message(
            message.id,
            status="failed",
            metadata={"error": f"Backend not found: {provider}"},
        )
        raise ValueError(f"Backend not found: {provider}")

    start_time = time.time()

    # Broadcast provider started event
    await self._broadcast(WebSocketEvent(
        type="discussion_provider_started",
        data={
            "session_id": session.id,
            "message_id": message.id,
            "provider": provider,
            "round": message.round_number,
            "message_type": message.message_type.value,
        },
    ))

    try:
        # Create gateway request
        request = GatewayRequest.create(
            provider=provider,
            message=prompt,
            timeout_s=session.config.provider_timeout_s,
        )

        # Execute with timeout
        result = await asyncio.wait_for(
            backend.execute(request),
            timeout=session.config.provider_timeout_s,
        )

        latency_ms = (time.time() - start_time) * 1000

        if result.success:
            self.store.update_discussion_message(
                message.id,
                content=result.response,
                status="completed",
                latency_ms=latency_ms,
            )
            message.content = result.response
            message.status = "completed"
            message.latency_ms = latency_ms

            # Broadcast provider completed event with content preview
            content_preview = (result.response or "")[:200]
            if len(result.response or "") > 200:
                content_preview += "..."

            await self._broadcast(WebSocketEvent(
                type="discussion_provider_completed",
                data={
                    "session_id": session.id,
                    "message_id": message.id,
                    "provider": provider,
                    "round": message.round_number,
                    "message_type": message.message_type.value,
                    "latency_ms": latency_ms,
                    "content_preview": content_preview,
                    "content_length": len(result.response or ""),
                    "success": True,
                },
            ))
        else:
            self.store.update_discussion_message(
                message.id,
                status="failed",
                latency_ms=latency_ms,
                metadata={"error": result.error},
            )

            # Broadcast provider failed event
            await self._broadcast(WebSocketEvent(
                type="discussion_provider_completed",
                data={
                    "session_id": session.id,
                    "message_id": message.id,
                    "provider": provider,
                    "round": message.round_number,
                    "latency_ms": latency_ms,
                    "success": False,
                    "error": result.error,
                },
            ))

            raise ValueError(f"Provider {provider} failed: {result.error}")

    except asyncio.TimeoutError:
        latency_ms = (time.time() - start_time) * 1000
        self.store.update_discussion_message(
            message.id,
            status="timeout",
            latency_ms=latency_ms,
        )

        # Broadcast timeout event
        await self._broadcast(WebSocketEvent(
            type="discussion_provider_completed",
            data={
                "session_id": session.id,
                "message_id": message.id,
                "provider": provider,
                "round": message.round_number,
                "latency_ms": latency_ms,
                "success": False,
                "error": "timeout",
            },
        ))

        raise ValueError(f"Provider {provider} timed out")

    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        latency_ms = (time.time() - start_time) * 1000
        self.store.update_discussion_message(
            message.id,
            status="failed",
            latency_ms=latency_ms,
            metadata={"error": str(e)},
        )

        # Broadcast error event
        await self._broadcast(WebSocketEvent(
            type="discussion_provider_completed",
            data={
                "session_id": session.id,
                "message_id": message.id,
                "provider": provider,
                "round": message.round_number,
                "latency_ms": latency_ms,
                "success": False,
                "error": str(e),
            },
        ))

        raise

    return message

async def _generate_summary_impl(self, session: DiscussionSession) -> str:
    """Generate final summary of the discussion."""
    self.store.update_discussion_session(
        session.id,
        status=DiscussionStatus.SUMMARIZING,
    )

    await self._broadcast(WebSocketEvent(
        type="discussion_summarizing",
        data={"session_id": session.id},
    ))

    # Get all messages
    all_messages = self.store.get_discussion_messages(session.id)

    # Build summary prompt
    prompt = self.prompt_builder.build_summary_prompt(session, all_messages)

    # Use first available provider or configured summary provider
    summary_provider = session.config.summary_provider
    if not summary_provider or summary_provider not in self.backends:
        summary_provider = session.providers[0]

    backend = self.backends.get(summary_provider)
    if not backend:
        raise ValueError(f"No backend available for summary")

    # Execute summary request
    request = GatewayRequest.create(
        provider=summary_provider,
        message=prompt,
        timeout_s=session.config.provider_timeout_s * 2,  # Extra time for summary
    )

    result = await asyncio.wait_for(
        backend.execute(request),
        timeout=session.config.provider_timeout_s * 2,
    )

    if not result.success:
        raise ValueError(f"Summary generation failed: {result.error}")

    # Save summary
    self.store.update_discussion_session(
        session.id,
        summary=result.response,
    )

    # Create summary message
    summary_message = DiscussionMessage.create(
        session_id=session.id,
        round_number=0,  # Special round for summary
        provider=summary_provider,
        message_type=MessageType.SUMMARY,
    )
    summary_message.content = result.response
    summary_message.status = "completed"
    self.store.create_discussion_message(summary_message)

    await self._broadcast(WebSocketEvent(
        type="discussion_summary_completed",
        data={
            "session_id": session.id,
            "summary_provider": summary_provider,
        },
    ))

    return result.response

