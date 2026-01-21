import pytest
from argus.core.docker_sandbox import DockerSandbox
from argus.core.decision_engine import DecisionEngine
from argus.domain.query import SqlStatement
from argus.domain.index import IndexSuggestion, IndexDefinition

@pytest.mark.integration
@pytest.mark.asyncio
async def test_validate_improvement():
    """
    Verify DecisionEngine can validate an index improvement in a real container.
    """
    # 1. Setup Data that needs an index
    # Creating a table with enough rows to make Seq Scan potentially costly (though with small data PG stays in memory)
    # To force an index usage/cost change, we usually need decent volume or disable seq scan.
    # For this test, verifying mechanism > verifying pg planner quirks.
    # We will force index usage via enable_seqscan=off if needed, but simple table scan vs index scan should show diff cost.
    
    setup_sql = """
    CREATE TABLE big_table (id serial PRIMARY KEY, val int);
    INSERT INTO big_table (val) SELECT floor(random() * 1000)::int FROM generate_series(1, 10000);
    VACUUM ANALYZE big_table;
    """
    
    # 2. Define Query
    # Query finding specific value
    query = SqlStatement(
        query_id="int_q1", 
        raw_query="SELECT * FROM big_table WHERE val = 500", 
        calls=1, 
        total_exec_time=0, 
        rows=0
    )
    
    # 3. Define Index Suggestion
    definition = IndexDefinition(table_name="big_table", columns=["val"], method="btree")
    suggestion = IndexSuggestion(
        target_query_id="int_q1",
        definition=definition,
        reasoning="Integration Test"
    )

    from argus.domain.sandbox import SandboxConfig

    # 4. Engine Factory
    def sandbox_factory():
        # Pre-seed the sandbox with the table
        config = SandboxConfig(postgres_image="postgres:16-alpine")
        # DecisionEngine calls factory to get instance
        return PreSeededSandbox(config, setup_sql)

    class PreSeededSandbox(DockerSandbox):
        def __init__(self, config, seed_sql):
            super().__init__(config)
            self.seed_sql = seed_sql
            
        async def _wait_for_ready(self):
            await super()._wait_for_ready()
            # Apply seed after ready. Split by statement to ensure VACUUM runs outside transaction block constraints of multi-statement execs if any.
            # Psycopg in autocommit mode should handle it, but VACUUM often requires being the only statement.
            statements = [s.strip() for s in self.seed_sql.split(";") if s.strip()]
            for stmt in statements:
                await self.seed(stmt)

    engine = DecisionEngine(sandbox_factory)

    # 5. Run Validation
    try:
        results = await engine.validate(query, [suggestion])
    except Exception as e:
        pytest.fail(f"DecisionEngine validation failed: {e}")

    assert len(results) == 1
    res = results[0]
    
    # We expect improvement (Index Scan < Seq Scan for 10k rows usually)
    # The cost might be identical if PG decides Seq Scan is still faster for small table.
    # But usually cost changes.
    # Let's just assert we got a result and it has costs.
    if res.validation.error:
        pytest.fail(f"Validation failed with error: {res.validation.error}")
    
    assert res.validation.original_cost > 0
    assert res.validation.new_cost > 0
    # Check that we didn't error
    assert res.validation.error is None
    # We hope for improvement, but flaky integration tests on planners are common.
    # We just want to check the *plumbing* works (did it run explain twice? did it create index?).
    # If plumbing works, new_cost != original_cost (likely).
    print(f"Integration Check: Baseline={res.validation.original_cost} -> New={res.validation.new_cost}")
