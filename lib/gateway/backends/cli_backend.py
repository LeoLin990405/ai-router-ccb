"""Compatibility shim for legacy ``gateway.backends.cli_backend`` imports."""

from .cli import CLIBackend


def __getattr__(name: str):
    if name != "InteractiveCLIBackend":
        raise AttributeError(name)
    from .interactive_cli_backend import InteractiveCLIBackend

    return InteractiveCLIBackend

__all__ = ["CLIBackend", "InteractiveCLIBackend"]
