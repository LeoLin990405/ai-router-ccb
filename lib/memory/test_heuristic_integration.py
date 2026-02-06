#!/usr/bin/env python3
"""
CCB Memory System v2.0 - Integration Test

Tests all major components of the heuristic memory system:
1. HeuristicRetriever - αR + βI + γT scoring
2. Access tracking
3. Importance management
4. Consolidator System 2 features
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

def test_heuristic_retriever():
    """Test HeuristicRetriever functionality."""
    print("=" * 60)
    print("Test 1: HeuristicRetriever")
    print("=" * 60)

    from memory.heuristic_retriever import HeuristicRetriever, RetrievalConfig

    # Test config loading
    config = RetrievalConfig.from_file()
    print(f"  Config loaded: α={config.alpha}, β={config.beta}, γ={config.gamma}")
    assert config.alpha + config.beta + config.gamma == 1.0, "Weights should sum to 1.0"
    print("  ✓ Config validation passed")

    # Test retriever initialization
    retriever = HeuristicRetriever()
    print("  ✓ Retriever initialized")

    # Test search
    results = retriever.retrieve("test", limit=5)
    print(f"  ✓ Search executed (found {len(results)} results)")

    # Test importance setting
    success = retriever.set_importance("test-memory-001", "message", 0.8, "test")
    print(f"  ✓ Set importance: {success}")

    # Test importance boost
    new_score = retriever.boost_importance("test-memory-001", "message", 0.05)
    print(f"  ✓ Boost importance: {new_score:.2f}")

    # Test statistics
    stats = retriever.get_statistics()
    print(f"  ✓ Statistics: {stats.get('tracked_memories', 0)} tracked memories")

    print()


def test_memory_v2():
    """Test CCBMemoryV2 with heuristic features."""
    print("=" * 60)
    print("Test 2: CCBMemoryV2 Heuristic Features")
    print("=" * 60)

    from memory.memory_v2 import CCBMemoryV2

    memory = CCBMemoryV2()
    print("  ✓ CCBMemoryV2 initialized")

    # Test log_access
    success = memory.log_access(
        memory_id="test-002",
        memory_type="message",
        access_context="test",
        query_text="test query"
    )
    print(f"  ✓ log_access: {success}")

    # Test set_importance
    success = memory.set_importance("test-002", "message", 0.7)
    print(f"  ✓ set_importance: {success}")

    # Test get_importance
    imp_data = memory.get_importance("test-002", "message")
    print(f"  ✓ get_importance: {imp_data.get('importance_score', 0):.2f}")

    # Test mark_for_forgetting
    success = memory.mark_for_forgetting("test-003", "message", reason="test")
    print(f"  ✓ mark_for_forgetting: {success}")

    # Test search_with_scores
    results = memory.search_with_scores("test", limit=3)
    print(f"  ✓ search_with_scores: {len(results)} results")

    # Test extended stats
    stats = memory.get_memory_stats_v2()
    heuristic = stats.get('heuristic', {})
    print(f"  ✓ get_memory_stats_v2: {heuristic.get('tracked_memories', 0)} tracked")

    print()


def test_consolidator():
    """Test NightlyConsolidator System 2 features."""
    print("=" * 60)
    print("Test 3: NightlyConsolidator System 2")
    print("=" * 60)

    from memory.consolidator import NightlyConsolidator

    consolidator = NightlyConsolidator()
    print("  ✓ NightlyConsolidator initialized")

    # Test decay application
    decay_result = consolidator.apply_decay_to_all(batch_size=100)
    print(f"  ✓ apply_decay_to_all: {decay_result.get('processed', 0)} processed")

    # Test forget expired
    forget_result = consolidator.forget_expired_memories(max_age_days=90)
    print(f"  ✓ forget_expired_memories: {forget_result.get('forgotten_count', 0)} forgotten")

    # Test consolidation stats
    stats = consolidator.get_consolidation_stats()
    print(f"  ✓ get_consolidation_stats: {stats.get('total_consolidations', 0)} total")

    print()


def test_config():
    """Test heuristic config file."""
    print("=" * 60)
    print("Test 4: Heuristic Config")
    print("=" * 60)

    config_path = Path.home() / ".ccb" / "heuristic_config.json"

    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)

        print(f"  ✓ Config file exists")
        print(f"  ✓ Version: {config.get('version', 'unknown')}")

        retrieval = config.get('retrieval', {})
        print(f"  ✓ Weights: α={retrieval.get('relevance_weight')}, β={retrieval.get('importance_weight')}, γ={retrieval.get('recency_weight')}")

        decay = config.get('decay', {})
        print(f"  ✓ Decay: λ={decay.get('lambda')}, max_age={decay.get('max_age_days')} days")

        system2 = config.get('system2', {})
        print(f"  ✓ System2: merge_threshold={system2.get('merge_similarity_threshold')}")
    else:
        print(f"  ✗ Config file not found at {config_path}")
        assert False, f"Config file not found at {config_path}"

    print()


def test_database_schema():
    """Test database schema has required tables."""
    print("=" * 60)
    print("Test 5: Database Schema")
    print("=" * 60)

    import sqlite3

    db_path = Path.home() / ".ccb" / "ccb_memory.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    required_tables = [
        'memory_importance',
        'memory_access_log',
        'consolidation_log'
    ]

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [row[0] for row in cursor.fetchall()]

    for table in required_tables:
        if table in existing_tables:
            print(f"  ✓ {table}")
        else:
            print(f"  ✗ {table} (MISSING)")
            assert False, f"Required table {table} is missing"

    conn.close()
    print()


def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     CCB Memory System v2.0 - Integration Test            ║")
    print("║     Heuristic Retrieval: αR + βI + γT                    ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"Test started at: {datetime.now().isoformat()}")
    print()

    results = []

    tests = [
        ("Database Schema", test_database_schema),
        ("Heuristic Config", test_config),
        ("HeuristicRetriever", test_heuristic_retriever),
        ("CCBMemoryV2 Features", test_memory_v2),
        ("NightlyConsolidator", test_consolidator),
    ]

    for name, test_func in tests:
        try:
            test_func()
            results.append((name, True))
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results.append((name, False))

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, s in results if s)
    total = len(results)

    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}  {name}")

    print()
    print(f"Total: {passed}/{total} tests passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
