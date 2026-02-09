"""
macOS Notification Manager for CCB Gateway.

Provides system notifications for long-running operations.
"""
from __future__ import annotations

import subprocess
import asyncio
from typing import Optional
import sys


class NotificationManager:
    """
    Manages macOS system notifications.

    Uses osascript to display native macOS notifications.
    Falls back gracefully on non-macOS systems.
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize the notification manager.

        Args:
            enabled: Whether notifications are enabled
        """
        self.enabled = enabled and sys.platform == "darwin"
        self._min_duration_for_notification = 60.0  # seconds

    def notify(
        self,
        title: str,
        message: str,
        subtitle: Optional[str] = None,
        sound: bool = True,
    ) -> bool:
        """
        Display a macOS notification.

        Args:
            title: Notification title
            message: Notification body
            subtitle: Optional subtitle
            sound: Whether to play notification sound

        Returns:
            True if notification was sent successfully
        """
        if not self.enabled:
            return False

        try:
            # Build AppleScript command
            script_parts = [f'display notification "{self._escape(message)}"']
            script_parts.append(f'with title "{self._escape(title)}"')

            if subtitle:
                script_parts.append(f'subtitle "{self._escape(subtitle)}"')

            if sound:
                script_parts.append('sound name "Glass"')

            script = " ".join(script_parts)

            # Execute via osascript
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=5.0,
            )
            return True

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError):
            return False

    def _escape(self, text: str) -> str:
        """Escape special characters for AppleScript."""
        return text.replace('"', '\\"').replace("\\", "\\\\")

    def notify_discussion_complete(
        self,
        session_id: str,
        topic: str,
        providers: list,
        duration_s: float,
    ) -> bool:
        """
        Send notification when a discussion completes.

        Args:
            session_id: Discussion session ID
            topic: Discussion topic
            providers: List of participating providers
            duration_s: Total duration in seconds
        """
        if duration_s < self._min_duration_for_notification:
            return False

        # Truncate topic if too long
        topic_display = topic[:50] + "..." if len(topic) > 50 else topic

        return self.notify(
            title="CCB Discussion Complete",
            message=topic_display,
            subtitle=f"{len(providers)} providers • {duration_s:.0f}s",
        )

    def notify_request_complete(
        self,
        request_id: str,
        provider: str,
        duration_s: float,
        success: bool = True,
    ) -> bool:
        """
        Send notification when a long request completes.

        Args:
            request_id: Request ID
            provider: Provider name
            duration_s: Request duration in seconds
            success: Whether the request succeeded
        """
        if duration_s < self._min_duration_for_notification:
            return False

        status = "✓ Complete" if success else "✗ Failed"

        return self.notify(
            title=f"CCB Request {status}",
            message=f"Provider: {provider}",
            subtitle=f"ID: {request_id[:8]} • {duration_s:.0f}s",
        )

    def notify_error(
        self,
        title: str,
        error: str,
    ) -> bool:
        """
        Send error notification.

        Args:
            title: Error title
            error: Error message
        """
        error_display = error[:100] + "..." if len(error) > 100 else error

        return self.notify(
            title=f"⚠️ {title}",
            message=error_display,
            sound=True,
        )

    async def notify_async(
        self,
        title: str,
        message: str,
        subtitle: Optional[str] = None,
    ) -> bool:
        """
        Send notification asynchronously.

        Args:
            title: Notification title
            message: Notification body
            subtitle: Optional subtitle

        Returns:
            True if notification was sent successfully
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.notify(title, message, subtitle),
        )


# Global notification manager instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager(enabled: bool = True) -> NotificationManager:
    """Get or create the global notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager(enabled=enabled)
    return _notification_manager
