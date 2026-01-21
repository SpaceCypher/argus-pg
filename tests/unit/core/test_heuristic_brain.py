import pytest

from argus.core.heuristic_brain import HeuristicBrain
from argus.domain.plans import ExplainPlan, PlanNode
from argus.domain.query import SqlStatement


@pytest.mark.asyncio
async def test_heuristic_brain_seq_scan_filter():
    """Test that HeuristicBrain suggests index for Seq Scan with Filter."""
    brain = HeuristicBrain()

    query = SqlStatement(
        query_id="q1",
        raw_query="SELECT * FROM users WHERE age > 30",
        calls=1,
        total_exec_time=10.0,
        rows=100,
    )

    plan = ExplainPlan(
        plan=PlanNode(
            node_type="Seq Scan",
            total_cost=100.0,
            startup_cost=0.0,
            plan_rows=100,
            plan_width=4,
            relation_name="users",
            filter_condition="(age > 30)",
        )
    )

    suggestions = await brain.propose_indexes(query, plan)

    assert len(suggestions) == 1
    sugg = suggestions[0]
    assert sugg.definition.table_name == "users"
    # columns is a list
    assert "age" in sugg.definition.columns
    assert sugg.definition.method == "btree"


@pytest.mark.asyncio
async def test_heuristic_brain_ignores_no_filter():
    """Test that HeuristicBrain ignores Seq Scan with NO filter."""
    brain = HeuristicBrain()

    query = SqlStatement(
        query_id="q2",
        raw_query="SELECT * FROM users",
        calls=1,
        total_exec_time=1.0,
        rows=100,
    )

    plan = ExplainPlan(
        plan=PlanNode(
            node_type="Seq Scan",
            total_cost=100.0,
            startup_cost=0.0,
            plan_rows=100,
            plan_width=4,
            relation_name="users",
            filter_condition=None,  # No filter
        )
    )

    suggestions = await brain.propose_indexes(query, plan)
    assert len(suggestions) == 0
