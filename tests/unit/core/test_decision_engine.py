from unittest.mock import AsyncMock, MagicMock

import pytest

from argus.core.decision_engine import DecisionEngine
from argus.core.sandbox import Sandbox
from argus.domain.index import IndexDefinition, IndexSuggestion
from argus.domain.query import SqlStatement


@pytest.mark.asyncio
async def test_decision_engine_validate_improvement():
    """Test validations when index improves performance."""

    # Mock Sandbox
    mock_sandbox = AsyncMock(spec=Sandbox)

    # Mock ExecutionStats object
    baseline_stats = MagicMock()
    baseline_stats.total_exec_time = 100.0

    improved_stats = MagicMock()
    improved_stats.total_exec_time = 50.0

    # 1. Baseline: 100 cost
    # 2. Verify: 50 cost
    mock_sandbox.run_query.side_effect = [
        baseline_stats,  # Baseline
        improved_stats,  # With Index
    ]

    # Factory logic
    async def mock_factory_logic():
        yield mock_sandbox

    # We need a proper context manager factory
    class MockSandboxFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return mock_sandbox

        async def __aexit__(self, exc_type, exc, tb):
            pass

    engine = DecisionEngine(MockSandboxFactory())

    query = SqlStatement(
        query_id="q1",
        raw_query="SELECT * FROM t1",
        calls=1,
        total_exec_time=10.0,
        rows=10,
    )

    definition = IndexDefinition(table_name="t1", columns=["c1"], method="btree")
    suggestion = IndexSuggestion(
        target_query_id="q1", definition=definition, reasoning="Test"
    )

    results = await engine.validate(query, [suggestion])

    assert len(results) == 1
    res = results[0]
    assert res.validation.improved is True
    assert res.validation.original_cost == 100.0
    assert res.validation.new_cost == 50.0
    assert res.validation.improvement_factor == 2.0

    # Verify calls
    # 1. run_query (Baseline)
    # 2. apply_index (Index)
    # 3. run_query (With Index)
    # 4. seed (DROP INDEX - cleanup). Note: decision_engine uses seed() for raw SQL DDL if run_command is structured differently
    # Let's check the implementation: decision_engine calls apply_index(def) and seed(drop_sql).

    assert mock_sandbox.run_query.call_count == 2
    assert mock_sandbox.apply_index.call_count == 1
    assert mock_sandbox.seed.call_count == 1

    # Check DDL in seed (Drop)
    assert "DROP INDEX" in mock_sandbox.seed.call_args_list[0][0][0]


@pytest.mark.asyncio
async def test_decision_engine_validate_degradation():
    """Test validations when index degrades performance (or no change)."""

    mock_sandbox = AsyncMock(spec=Sandbox)

    stats_100 = MagicMock()
    stats_100.total_exec_time = 100.0

    # No improvement: 100 -> 100
    mock_sandbox.run_query.side_effect = [
        stats_100,
        stats_100,
    ]

    class MockSandboxFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return mock_sandbox

        async def __aexit__(self, exc_type, exc, tb):
            pass

    engine = DecisionEngine(MockSandboxFactory())

    query = SqlStatement(
        query_id="q1",
        raw_query="SELECT * FROM t1",
        calls=1,
        total_exec_time=10.0,
        rows=10,
    )

    definition = IndexDefinition(table_name="t1", columns=["c1"], method="btree")
    suggestion = IndexSuggestion(
        target_query_id="q1", definition=definition, reasoning="Test"
    )

    results = await engine.validate(query, [suggestion])

    assert len(results) == 1
    res = results[0]
    assert res.validation.improved is False
    assert res.validation.improvement_factor == 1.0
