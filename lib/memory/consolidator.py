#!/usr/bin/env python3
"""Memory Consolidator facade with modularized mixins."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from .consolidator_bootstrap import ConsolidatorBootstrapMixin
from .consolidator_core import ConsolidatorCoreMixin
from .consolidator_heuristics_abstract import ConsolidatorHeuristicsAbstractMixin
from .consolidator_heuristics_runtime import ConsolidatorHeuristicsRuntimeMixin
from .consolidator_llm import ConsolidatorLLMMixin
from .consolidator_models import SessionArchive


def _emit(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")


class NightlyConsolidator(
    ConsolidatorBootstrapMixin,
    ConsolidatorLLMMixin,
    ConsolidatorCoreMixin,
    ConsolidatorHeuristicsRuntimeMixin,
    ConsolidatorHeuristicsAbstractMixin,
):
    """System 2: Consolidates session archives into structured long-term memory."""

    GATEWAY_URL = "http://localhost:8765"
    DEFAULT_LLM_PROVIDER = "kimi"
    DB_PATH = Path.home() / ".ccb" / "ccb_memory.db"


def main():
    """CLI entry point for consolidator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Consolidate session archives into long-term memory"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours to look back (default: 24)"
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        help="Archive directory (default: ~/.ccb/context_archive)"
    )
    parser.add_argument(
        "--memory-dir",
        type=Path,
        help="Memory output directory (default: ~/.ccb/memories)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON to stdout instead of saving"
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Use LLM for enhanced consolidation (Phase 3)"
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        default="kimi",
        help="LLM provider for consolidation (default: kimi)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without saving (for testing)"
    )

    args = parser.parse_args()

    consolidator = NightlyConsolidator(
        archive_dir=args.archive_dir,
        memory_dir=args.memory_dir,
        llm_provider=args.llm_provider
    )

    # Choose consolidation method
    if args.llm:
        # Use LLM-enhanced consolidation
        memory = asyncio.run(consolidator.consolidate_with_llm(hours=args.hours))
    else:
        # Basic consolidation
        memory = consolidator.consolidate(hours=args.hours)

    if args.json or args.dry_run:
        _emit(json.dumps(memory, ensure_ascii=False, indent=2))
    elif memory.get("status") == "no_sessions":
        _emit("No sessions found in the specified time range")
        sys.exit(0)
    else:
        if memory.get("llm_enhanced"):
            _emit("✓ LLM-enhanced consolidation complete")
            _emit(f"  - Learnings: {len(memory.get('llm_learnings', []))}")
            _emit(f"  - Preferences: {len(memory.get('llm_preferences', []))}")
            _emit(f"  - Patterns: {len(memory.get('llm_patterns', []))}")
        else:
            _emit("✓ Basic consolidation complete")
            if memory.get("llm_error"):
                _emit(f"  ⚠ LLM error: {memory.get('llm_error')}")


if __name__ == "__main__":
    main()
