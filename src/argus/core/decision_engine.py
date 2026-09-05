import logging
from collections.abc import Callable

from argus.core.hydrator import DataHydrator
from argus.core.sandbox import Sandbox
from argus.core.schema import SchemaExtractor
from argus.domain.index import (
    IndexSuggestion,
    MigrationPlan,
    ValidationResult,
    VerifiedIndexSuggestion,
)
from argus.domain.query import SqlStatement

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Orchestrates validation of suggestions.
    Manages sandbox lifecycle: clone schema & hydrate -> measure baseline -> apply -> measure -> revert.
    """

    def __init__(
        self,
        sandbox_factory: Callable[[], Sandbox],
        schema_extractor: SchemaExtractor | None = None,
        hydrator: DataHydrator | None = None,
    ):
        self.sandbox_factory = sandbox_factory
        self.schema_extractor = schema_extractor
        self.hydrator = hydrator or DataHydrator()

    async def validate(
        self,
        query: SqlStatement,
        suggestions: list[IndexSuggestion],
        seed_sql: str | None = None,
    ) -> list[VerifiedIndexSuggestion]:
        results: list[VerifiedIndexSuggestion] = []

        try:
            async with self.sandbox_factory() as sb:
                # 1. Setup Schema & Synthetic Data Hydration
                if seed_sql:
                    await sb.seed(seed_sql)
                elif self.schema_extractor:
                    try:
                        table_names = self.schema_extractor.extract_table_names(
                            query.raw_query
                        )
                        if table_names:
                            ddl = await self.schema_extractor.extract_schema_ddl(
                                table_names
                            )
                            if ddl:
                                await sb.seed(ddl)

                            predicates = DataHydrator.extract_predicates_from_query(
                                query.raw_query
                            )
                            for tbl in table_names:
                                meta = await self.schema_extractor.extract_table_schema(
                                    tbl
                                )
                                if meta:
                                    hydration_sql = (
                                        self.hydrator.generate_table_hydration_sql(
                                            table_meta=meta,
                                            row_count=20000,
                                            query_predicates=predicates,
                                        )
                                    )
                                    if hydration_sql:
                                        await sb.seed(hydration_sql)
                    except Exception as e:
                        logger.warning(
                            f"Schema cloning/hydration skipped or encountered warning: {e}"
                        )

                # 2. Baseline
                try:
                    await sb.reset_metrics()
                    baseline_stats = await sb.run_query(query)
                    baseline_cost = baseline_stats.total_exec_time
                except Exception as e:
                    logger.error(f"Baseline query failed: {e}")
                    return [
                        self._create_failed_result(s, 0.0, f"Baseline failed: {e}")
                        for s in suggestions
                    ]

                # 3. Test Each Suggestion
                for suggestion in suggestions:
                    name = suggestion.definition.inferred_name
                    # Build standard migration plan
                    cols = ", ".join(f'"{c}"' for c in suggestion.definition.columns)
                    unique_str = "UNIQUE " if suggestion.definition.unique else ""
                    up_sql = (
                        f"CREATE {unique_str}INDEX CONCURRENTLY {name} "
                        f'ON "{suggestion.definition.schema_name}"."{suggestion.definition.table_name}" '
                        f"USING {suggestion.definition.method} ({cols});"
                    )
                    down_sql = f'DROP INDEX CONCURRENTLY IF EXISTS "{suggestion.definition.schema_name}"."{name}";'
                    migration = MigrationPlan(
                        up_sql=up_sql, down_sql=down_sql, transactional=False
                    )

                    try:
                        # Apply Index
                        await sb.apply_index(suggestion.definition)

                        # Measure with Index
                        await sb.reset_metrics()
                        new_stats = await sb.run_query(query)
                        new_cost = new_stats.total_exec_time

                        # Calculate Improvement
                        if new_cost > 0:
                            factor = baseline_cost / new_cost
                        else:
                            factor = 999.0 if baseline_cost > 0 else 1.0

                        improved = factor > 1.0

                        results.append(
                            VerifiedIndexSuggestion(
                                target_query_id=suggestion.target_query_id,
                                definition=suggestion.definition,
                                reasoning=suggestion.reasoning,
                                migration=migration,
                                validation=ValidationResult(
                                    improved=improved,
                                    original_cost=baseline_cost,
                                    new_cost=new_cost,
                                    improvement_factor=factor,
                                ),
                            )
                        )

                        # Revert (Drop Index)
                        schema = suggestion.definition.schema_name
                        drop_sql = f'DROP INDEX IF EXISTS "{schema}"."{name}";'
                        await sb.seed(drop_sql)

                    except Exception as e:
                        logger.warning(f"Validation failed for {name}: {e}")
                        results.append(
                            self._create_failed_result(
                                suggestion, baseline_cost, str(e), migration=migration
                            )
                        )

        except Exception as e:
            logger.error(f"Sandbox lifecycle failed: {e}")
            for s in suggestions:
                if s.definition.inferred_name not in [
                    r.definition.inferred_name for r in results
                ]:
                    results.append(
                        self._create_failed_result(s, 0.0, f"Sandbox error: {e}")
                    )

        return results

    def _create_failed_result(
        self,
        suggestion: IndexSuggestion,
        original_cost: float,
        error: str,
        migration: MigrationPlan | None = None,
    ) -> VerifiedIndexSuggestion:
        return VerifiedIndexSuggestion(
            target_query_id=suggestion.target_query_id,
            definition=suggestion.definition,
            reasoning=suggestion.reasoning,
            migration=migration,
            validation=ValidationResult(
                improved=False,
                original_cost=original_cost,
                new_cost=0.0,
                improvement_factor=1.0,
                error=error,
            ),
        )
