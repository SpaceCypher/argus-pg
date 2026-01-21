from argus.core.analyzer import Analyzer
from argus.domain.plans import ExplainPlan, PlanNode


def test_analyzer_parsing_basic():
    """Test basic parsing and node finding."""
    # Mock Plan Structure
    mock_plan = ExplainPlan(
        plan=PlanNode(
            node_type="Seq Scan",
            total_cost=100.0,
            startup_cost=0.0,
            plan_rows=100,
            plan_width=4,
            plans=[],
            relation_name="users",
            alias="u",
            filter_condition="(age > 30)",
        )
    )

    analyzer = Analyzer(mock_plan)

    # Test find_nodes
    seq_scans = analyzer.find_nodes("Seq Scan")
    assert len(seq_scans) == 1
    assert seq_scans[0].relation_name == "users"

    # Test get_total_cost
    assert analyzer.get_total_cost() == 100.0


def test_analyzer_nested_nodes():
    """Test finding nodes in a nested plan tree."""
    # Nested Plan: Hash Join -> [Seq Scan, Seq Scan]
    mock_plan = ExplainPlan(
        plan=PlanNode(
            node_type="Hash Join",
            total_cost=200.0,
            startup_cost=10.0,
            plan_rows=200,
            plan_width=8,
            plans=[
                PlanNode(
                    node_type="Seq Scan",
                    total_cost=50.0,
                    startup_cost=0.0,
                    plan_rows=100,
                    plan_width=4,
                    relation_name="t1",
                ),
                PlanNode(
                    node_type="Seq Scan",
                    total_cost=50.0,
                    startup_cost=0.0,
                    plan_rows=100,
                    plan_width=4,
                    relation_name="t2",
                ),
            ],
        )
    )

    analyzer = Analyzer(mock_plan)

    seq_scans = analyzer.find_nodes("Seq Scan")
    assert len(seq_scans) == 2
    names = {n.relation_name for n in seq_scans}
    assert "t1" in names
    assert "t2" in names
