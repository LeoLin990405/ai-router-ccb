"""Compatibility shim for legacy ``gateway.gateway_server`` module path."""

from .server import GatewayServer, run_gateway

__all__ = ["GatewayServer", "run_gateway"]


if __name__ == "__main__":
    run_gateway()

