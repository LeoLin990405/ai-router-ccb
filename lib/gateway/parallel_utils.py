"""Utility helpers for parallel execution aggregation."""
from __future__ import annotations

from typing import Any, Dict, List

def parse_provider_spec(spec: str, provider_groups: Dict[str, List[str]]) -> tuple[List[str], bool]:
    """
    Parse a provider specification.

    Args:
        spec: Provider spec (e.g., "claude", "@all", "@fast")
        provider_groups: Dict of group name -> provider list

    Returns:
        Tuple of (provider_list, is_parallel)
    """
    if spec.startswith("@"):
        group_name = spec[1:]
        providers = provider_groups.get(group_name, [])
        return providers, len(providers) > 1
    else:
        return [spec], False



def compare_responses(responses: List[str]) -> Dict[str, Any]:
    """
    Compare multiple responses for similarity analysis.

    Args:
        responses: List of response strings

    Returns:
        Dict with comparison metrics
    """
    if not responses:
        return {"count": 0, "avg_length": 0, "length_variance": 0}

    lengths = [len(r) for r in responses]
    avg_length = sum(lengths) / len(lengths)
    variance = sum((l - avg_length) ** 2 for l in lengths) / len(lengths)

    return {
        "count": len(responses),
        "avg_length": avg_length,
        "length_variance": variance,
        "min_length": min(lengths),
        "max_length": max(lengths),
    }


# Import GatewayRequest for type checking
from .models import GatewayRequest

