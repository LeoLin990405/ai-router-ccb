"""
Hooks Manager for CCB

Provides event-driven hooks for extending CCB functionality.
"""
from __future__ import annotations

import asyncio
import importlib.util
import traceback
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Union


def _warn(message: str) -> None:
    sys.stderr.write(f"{message}\n")


HANDLED_EXCEPTIONS = (Exception,)


class HookEvent(Enum):
    """Available hook events."""
    PRE_REQUEST = "pre_request"
    POST_RESPONSE = "post_response"
    ON_ERROR = "on_error"
    ON_RATE_LIMIT = "on_rate_limit"
    ON_PROVIDER_SWITCH = "on_provider_switch"
    ON_CACHE_HIT = "on_cache_hit"
    ON_AGENT_START = "on_agent_start"
    ON_AGENT_COMPLETE = "on_agent_complete"


@dataclass
class HookContext:
    """Context passed to hook handlers."""
    event: HookEvent
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        import time
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class HookResult:
    """Result from a hook execution."""
    success: bool
    modified_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    hook_name: str = ""


@dataclass
class HookConfig:
    """Configuration for a hook."""
    name: str
    event: HookEvent
    handler: Callable
    priority: int = 100  # Lower = higher priority
    enabled: bool = True
    async_mode: bool = False


class HooksManager:
    """
    Hooks manager for CCB.

    Features:
    - Register hooks for various events
    - Priority-based execution order
    - Sync and async hook support
    - Hook chaining with data modification
    - Load hooks from directory
    """

    def __init__(self, hooks_dir: Optional[str] = None):
        """
        Initialize the hooks manager.

        Args:
            hooks_dir: Directory containing hook scripts
        """
        self._hooks: Dict[HookEvent, List[HookConfig]] = {
            event: [] for event in HookEvent
        }
        self._hooks_dir = hooks_dir or str(Path.home() / ".ccb_config" / "hooks")

    def register_hook(
        self,
        event: HookEvent,
        handler: Callable,
        name: Optional[str] = None,
        priority: int = 100,
        async_mode: bool = False,
    ) -> None:
        """
        Register a hook handler.

        Args:
            event: Event to hook
            handler: Handler function
            name: Hook name (auto-generated if not provided)
            priority: Execution priority (lower = earlier)
            async_mode: Whether handler is async
        """
        if name is None:
            name = f"{event.value}_{len(self._hooks[event])}"

        config = HookConfig(
            name=name,
            event=event,
            handler=handler,
            priority=priority,
            enabled=True,
            async_mode=async_mode,
        )

        self._hooks[event].append(config)
        # Sort by priority
        self._hooks[event].sort(key=lambda h: h.priority)

    def unregister_hook(self, event: HookEvent, name: str) -> bool:
        """
        Unregister a hook.

        Args:
            event: Event type
            name: Hook name

        Returns:
            True if hook was removed
        """
        hooks = self._hooks[event]
        for i, hook in enumerate(hooks):
            if hook.name == name:
                hooks.pop(i)
                return True
        return False

    def enable_hook(self, event: HookEvent, name: str) -> bool:
        """Enable a hook."""
        for hook in self._hooks[event]:
            if hook.name == name:
                hook.enabled = True
                return True
        return False

    def disable_hook(self, event: HookEvent, name: str) -> bool:
        """Disable a hook."""
        for hook in self._hooks[event]:
            if hook.name == name:
                hook.enabled = False
                return True
        return False

    def trigger(
        self,
        event: HookEvent,
        data: Optional[Dict[str, Any]] = None,
    ) -> List[HookResult]:
        """
        Trigger hooks for an event (synchronous).

        Args:
            event: Event to trigger
            data: Data to pass to hooks

        Returns:
            List of hook results
        """
        context = HookContext(event=event, data=data or {})
        results = []

        for hook in self._hooks[event]:
            if not hook.enabled:
                continue

            try:
                if hook.async_mode:
                    # Run async hook in event loop
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(
                            hook.handler(context)
                        )
                    finally:
                        loop.close()
                else:
                    result = hook.handler(context)

                # Handle result
                if isinstance(result, dict):
                    # Hook modified the data
                    context.data.update(result)
                    results.append(HookResult(
                        success=True,
                        modified_data=result,
                        hook_name=hook.name,
                    ))
                else:
                    results.append(HookResult(
                        success=True,
                        hook_name=hook.name,
                    ))

            except HANDLED_EXCEPTIONS as e:
                results.append(HookResult(
                    success=False,
                    error=str(e),
                    hook_name=hook.name,
                ))

        return results

    async def trigger_async(
        self,
        event: HookEvent,
        data: Optional[Dict[str, Any]] = None,
    ) -> List[HookResult]:
        """
        Trigger hooks for an event (asynchronous).

        Args:
            event: Event to trigger
            data: Data to pass to hooks

        Returns:
            List of hook results
        """
        context = HookContext(event=event, data=data or {})
        results = []

        for hook in self._hooks[event]:
            if not hook.enabled:
                continue

            try:
                if hook.async_mode:
                    result = await hook.handler(context)
                else:
                    result = hook.handler(context)

                if isinstance(result, dict):
                    context.data.update(result)
                    results.append(HookResult(
                        success=True,
                        modified_data=result,
                        hook_name=hook.name,
                    ))
                else:
                    results.append(HookResult(
                        success=True,
                        hook_name=hook.name,
                    ))

            except HANDLED_EXCEPTIONS as e:
                results.append(HookResult(
                    success=False,
                    error=str(e),
                    hook_name=hook.name,
                ))

        return results

    def list_hooks(self, event: Optional[HookEvent] = None) -> List[HookConfig]:
        """
        List registered hooks.

        Args:
            event: Filter by event (None for all)

        Returns:
            List of hook configurations
        """
        if event:
            return list(self._hooks[event])

        all_hooks = []
        for hooks in self._hooks.values():
            all_hooks.extend(hooks)
        return all_hooks

    def load_hooks_from_directory(self) -> int:
        """
        Load hooks from the hooks directory.

        Hook files should be Python files with a `register_hooks(manager)` function.

        Returns:
            Number of hooks loaded
        """
        hooks_path = Path(self._hooks_dir)
        if not hooks_path.exists():
            return 0

        count = 0
        for hook_file in hooks_path.glob("*.py"):
            try:
                spec = importlib.util.spec_from_file_location(
                    hook_file.stem, hook_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    if hasattr(module, "register_hooks"):
                        before = sum(len(h) for h in self._hooks.values())
                        module.register_hooks(self)
                        after = sum(len(h) for h in self._hooks.values())
                        count += after - before

            except HANDLED_EXCEPTIONS as e:
                _warn(f"Failed to load hook {hook_file}: {e}")

        return count

    def get_hook_stats(self) -> Dict[str, Any]:
        """Get statistics about registered hooks."""
        stats = {
            "total_hooks": 0,
            "enabled_hooks": 0,
            "disabled_hooks": 0,
            "by_event": {},
        }

        for event, hooks in self._hooks.items():
            enabled = sum(1 for h in hooks if h.enabled)
            disabled = len(hooks) - enabled

            stats["total_hooks"] += len(hooks)
            stats["enabled_hooks"] += enabled
            stats["disabled_hooks"] += disabled
            stats["by_event"][event.value] = {
                "total": len(hooks),
                "enabled": enabled,
                "disabled": disabled,
            }

        return stats


# Singleton instance
_hooks_manager: Optional[HooksManager] = None


def get_hooks_manager() -> HooksManager:
    """Get the global hooks manager instance."""
    global _hooks_manager
    if _hooks_manager is None:
        _hooks_manager = HooksManager()
    return _hooks_manager


# Decorator for easy hook registration
def hook(
    event: HookEvent,
    priority: int = 100,
    name: Optional[str] = None,
):
    """
    Decorator to register a function as a hook.

    Usage:
        @hook(HookEvent.PRE_REQUEST)
        def my_hook(context: HookContext):
            _warn(f"Request: {context.data}")
    """
    def decorator(func: Callable):
        manager = get_hooks_manager()
        hook_name = name or func.__name__
        is_async = asyncio.iscoroutinefunction(func)

        manager.register_hook(
            event=event,
            handler=func,
            name=hook_name,
            priority=priority,
            async_mode=is_async,
        )

        return func
    return decorator
