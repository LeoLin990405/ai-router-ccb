# CCB Memory System v2.0 - Implementation Summary

## Overview

Successfully implemented the CCB Memory System v2.0 architecture upgrade based on the design document. The system now features Stanford Generative Agents style heuristic retrieval with the αR + βI + γT scoring formula.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CCB Memory System v2.0                           │
├─────────────────────────────────────────────────────────────────────┤
│  System 1 (Fast Path) - <100ms latency                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  HeuristicRetriever: final_score = αR + βI + γT             │    │
│  │  - Relevance (R): FTS5 BM25 normalized                      │    │
│  │  - Importance (I): User/LLM scored (0.0-1.0)                │    │
│  │  - Recency (T): Ebbinghaus decay exp(-λ × hours)            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  System 2 (Slow Path) - Async/Nightly                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  NightlyConsolidator:                                        │    │
│  │  - Merge: Combine similar memories (threshold=0.9)           │    │
│  │  - Abstract: LLM-generated summaries for groups              │    │
│  │  - Forget: Clean up low-importance, old memories             │    │
│  │  - Decay: Apply time-based importance decay                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## Files Created/Modified

### New Files

| File | Purpose |
|------|---------|
| `lib/memory/heuristic_retriever.py` | Core αR + βI + γT retrieval implementation |
| `lib/memory/schema_v2_migration.sql` | Database schema for v2 tables |
| `lib/memory/test_heuristic_integration.py` | Integration tests |
| `scripts/ccb-consolidate` | System 2 CLI tool |
| `~/.ccb/heuristic_config.json` | Configuration file |

### Modified Files

| File | Changes |
|------|---------|
| `lib/memory/memory_v2.py` | Added access tracking, importance, decay methods |
| `lib/memory/consolidator.py` | Added merge, abstract, forget, decay methods |
| `lib/gateway/middleware/memory_middleware.py` | Integrated HeuristicRetriever |
| `scripts/ccb-mem` | Added v2.0 commands |

## New Database Tables

```sql
-- 1. Memory Importance (stores R/I/T scores)
memory_importance (
    memory_id TEXT PRIMARY KEY,
    memory_type TEXT,          -- 'message' | 'observation'
    importance_score REAL,     -- 0.0-1.0
    score_source TEXT,         -- 'user' | 'llm' | 'heuristic'
    last_accessed_at TEXT,
    access_count INTEGER,
    decay_rate REAL
)

-- 2. Memory Access Log (for recency calculation)
memory_access_log (
    memory_id TEXT,
    memory_type TEXT,
    accessed_at TEXT,
    access_context TEXT,       -- 'retrieval' | 'injection'
    request_id TEXT,
    relevance_score REAL
)

-- 3. Consolidation Log (System 2 operations)
consolidation_log (
    consolidation_type TEXT,   -- 'merge' | 'abstract' | 'forget'
    source_ids TEXT,           -- JSON array
    result_id TEXT,
    llm_provider TEXT,
    status TEXT
)
```

## CLI Commands

### ccb-mem (new commands)

```bash
# Set importance score
ccb-mem importance <memory_id> <score>  # 0.0-1.0

# Apply decay
ccb-mem decay --batch-size 1000

# Mark for forgetting
ccb-mem forget <memory_id>

# Search with scores
ccb-mem search-scored "query" --limit 10 --verbose

# Extended stats
ccb-mem stats-v2
```

### ccb-consolidate (new CLI)

```bash
# Run session consolidation
ccb-consolidate consolidate --hours 24 --llm

# Apply decay
ccb-consolidate decay --batch-size 1000

# Merge similar memories
ccb-consolidate merge --threshold 0.9

# Generate abstractions
ccb-consolidate abstract --min-group-size 5

# Clean up expired
ccb-consolidate forget --max-age-days 90

# Full nightly run
ccb-consolidate nightly

# View stats
ccb-consolidate stats
```

## Scoring Formula

```
final_score = α × relevance + β × importance + γ × recency

Where:
  α = 0.4 (relevance weight)
  β = 0.3 (importance weight)
  γ = 0.3 (recency weight)

recency = exp(-λ × hours_since_access)
  λ = 0.1 (decay rate)
```

## Configuration

Located at `~/.ccb/heuristic_config.json`:

```json
{
  "retrieval": {
    "relevance_weight": 0.4,
    "importance_weight": 0.3,
    "recency_weight": 0.3,
    "candidate_pool_size": 50,
    "final_limit": 5
  },
  "decay": {
    "lambda": 0.1,
    "min_score": 0.01,
    "max_age_days": 90
  },
  "system2": {
    "merge_similarity_threshold": 0.9,
    "abstract_group_min_size": 5,
    "llm_provider": "kimi"
  }
}
```

## Integration Points

1. **MemoryMiddleware**: Automatically uses HeuristicRetriever for context injection
2. **Gateway API**: Returns scored results with R/I/T values
3. **Access Tracking**: Automatic logging via database trigger
4. **System 2 Scheduler**: Can be run via cron or manual invocation

## Test Results

```
✓ PASS  Database Schema
✓ PASS  Heuristic Config
✓ PASS  HeuristicRetriever
✓ PASS  CCBMemoryV2 Features
✓ PASS  NightlyConsolidator

Total: 5/5 tests passed
```

## Usage Example

```python
from lib.memory.heuristic_retriever import HeuristicRetriever

# Initialize
retriever = HeuristicRetriever()

# Search with heuristic scoring
results = retriever.retrieve("python error handling", limit=5)

for mem in results:
    print(f"Score: {mem.final_score:.3f}")
    print(f"  R={mem.relevance_score:.2f}")
    print(f"  I={mem.importance_score:.2f}")
    print(f"  T={mem.recency_score:.2f}")
    print(f"  Content: {mem.content[:50]}...")

# Set importance manually
retriever.set_importance("memory-id", "message", 0.9, source="user")
```

## References

- Stanford Generative Agents: https://arxiv.org/pdf/2304.03442
- Ebbinghaus Forgetting Curve
- Awesome-AI-Memory: https://github.com/IAAR-Shanghai/Awesome-AI-Memory
