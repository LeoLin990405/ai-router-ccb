#!/usr/bin/env python3
"""Skills Discovery Service for CCB Gateway."""
from __future__ import annotations

from .skills_discovery_core import SkillsDiscoveryCoreMixin
from .skills_discovery_feedback import SkillsDiscoveryFeedbackMixin
from .skills_discovery_ranking import SkillsDiscoveryRankingMixin
from .skills_discovery_stats import SkillsDiscoveryStatsMixin


class SkillsDiscoveryService(
    SkillsDiscoveryCoreMixin,
    SkillsDiscoveryRankingMixin,
    SkillsDiscoveryFeedbackMixin,
    SkillsDiscoveryStatsMixin,
):
    """Discovers and manages Claude Code skills for CCB Gateway."""


# CLI interface
if __name__ == "__main__":
    import sys

    def _cli_emit(message: str = "") -> None:
        sys.stdout.write(f"{message}\n")

    service = SkillsDiscoveryService()

    if len(sys.argv) < 2:
        _cli_emit("Usage:")
        _cli_emit("  python3 skills_discovery.py scan          # Refresh cache")
        _cli_emit("  python3 skills_discovery.py match <task>  # Find matching skills")
        _cli_emit("  python3 skills_discovery.py stats         # Show usage stats")
        sys.exit(1)

    command = sys.argv[1]

    if command == "scan":
        service._refresh_cache()
        _cli_emit("✓ Skills cache refreshed")

    elif command == "match":
        if len(sys.argv) < 3:
            _cli_emit("Error: Please provide a task description")
            sys.exit(1)

        task = " ".join(sys.argv[2:])
        recommendations = service.get_recommendations(task)

        _cli_emit(f"\n{recommendations['message']}\n")

        for skill in recommendations['skills']:
            _cli_emit(f"  • {skill['name']} (score: {skill['relevance_score']})")
            _cli_emit(f"    {skill['description']}")
            if skill['installed']:
                _cli_emit(f"    Usage: {skill['usage_command']}")
            else:
                _cli_emit("    Not installed")
            _cli_emit()

    elif command == "stats":
        stats = service.get_stats()

        _cli_emit("\n📊 Skills Discovery Statistics\n")
        _cli_emit("=" * 40)

        # Cache stats
        cache = stats['cache']
        _cli_emit(f"\n📦 Skills Cache:")
        _cli_emit(f"   Total cached:  {cache['total']}")
        _cli_emit(f"   Installed:     {cache['installed']}")
        _cli_emit(f"   Local:         {cache['local']}")
        _cli_emit(f"   Remote:        {cache['remote']}")

        # Usage stats
        usage = stats['usage']
        _cli_emit(f"\n📈 Usage Statistics:")
        _cli_emit(f"   Total uses:    {usage['total_uses']}")
        _cli_emit(f"   Unique skills: {usage['unique_skills']}")
        _cli_emit(f"   Success rate:  {usage['success_rate']}%")
        _cli_emit(f"   Active days:   {usage['active_days']}")

        # Feedback stats
        feedback = stats['feedback']
        _cli_emit(f"\n⭐ Feedback Statistics:")
        _cli_emit(f"   Total feedback: {feedback['total']}")
        if feedback['avg_rating']:
            _cli_emit(f"   Avg rating:     {feedback['avg_rating']}/5")
        _cli_emit(f"   Helpful rate:   {feedback['helpful_rate']}%")

        # Top skills
        if stats['top_skills']:
            _cli_emit(f"\n🏆 Top Skills by Usage:")
            for i, skill in enumerate(stats['top_skills'], 1):
                _cli_emit(f"   {i}. {skill['name']} ({skill['uses']} uses)")

        _cli_emit("\n" + "=" * 40)

    else:
        _cli_emit(f"Unknown command: {command}")
        sys.exit(1)
