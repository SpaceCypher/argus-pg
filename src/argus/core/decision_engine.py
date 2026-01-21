import logging
from collections.abc import Callable

from argus.core.sandbox import Sandbox
from argus.domain.index import (
    IndexSuggestion,
    ValidationResult,
    VerifiedIndexSuggestion,
)
from argus.domain.query import SqlStatement

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Orchestrates validation of suggestions.
    Orchestrates validation of suggestions.
    Manages sandbox lifecycle: measure baseline -> apply -> measure -> revert.
    """

    def __init__(self, sandbox_factory: Callable[[], Sandbox]):
        self.sandbox_factory = sandbox_factory

    async def validate(
        self, query: SqlStatement, suggestions: list[IndexSuggestion]
    ) -> list[VerifiedIndexSuggestion]:
        results: list[VerifiedIndexSuggestion] = []

        # Using single sandbox session for validation batch.
        # Ideally use one sandbox per test for full isolation.
        # Assuming we can revert cleanly with drop index.

        try:
            async with self.sandbox_factory() as sb:
                # 1. Setup Data (Seed) - In a real scenario, we might need data.
                # 1. Setup Data - Assuming pre-seeded environment.
                # If tables missing, queries fail (baseline check catches this).
                # TODO: Implement schema cloning to sandbox.

                # 2. Baseline
                try:
                    baseline_stats = await sb.run_query(query)
                    baseline_cost = (
                        baseline_stats.total_exec_time
                    )  # Using time as proxy for cost/perf
                except Exception as e:
                    logger.error(f"Baseline query failed: {e}")
                    # If baseline fails, all suggestions fail
                    return [
                        self._create_failed_result(s, 0.0, f"Baseline failed: {e}")
                        for s in suggestions
                    ]

                for suggestion in suggestions:
                    try:
                        # 3. Apply Index
                        await sb.apply_index(suggestion.definition)

                        # 4. Measure
                        new_stats = await sb.run_query(query)
                        new_cost = new_stats.total_exec_time

                        # 5. Calculate Improvement
                        # Improvement factor: old / new. > 1.0 is better (speedup).
                        # Logic: if baseline=100ms, new=50ms, factor=2.0x
                        if new_cost > 0:
                            factor = baseline_cost / new_cost
                        else:
                            factor = 999.0  # Instant execution

                        improved = factor > 1.0

                        results.append(
                            VerifiedIndexSuggestion(
                                **suggestion.model_dump(),
                                validation=ValidationResult(
                                    improved=improved,
                                    original_cost=baseline_cost,
                                    new_cost=new_cost,
                                    improvement_factor=factor,
                                ),
                            )
                        )

                        # 6. Revert (Drop Index)
                        # Cleanup: Drop index to restore state.
                        schema = suggestion.definition.schema_name
                        name = suggestion.definition.inferred_name
                        drop_sql = f'DROP INDEX IF EXISTS "{schema}"."{name}";'
                        await sb.seed(drop_sql)

                    except Exception as e:
                        logger.warning(f"Validation failed for {name}: {e}")
                        results.append(
                            self._create_failed_result(
                                suggestion, baseline_cost, str(e)
                            )
                        )

        except Exception as e:
            logger.error(f"Sandbox lifecycle failed: {e}")
            # Fail all remaining
            for s in suggestions:
                if s not in [r for r in results]:  # inefficient check but list is small
                    results.append(
                        self._create_failed_result(s, 0.0, f"Sandbox error: {e}")
                    )

        return results

    def _create_failed_result(
        self, suggestion: IndexSuggestion, original_cost: float, error: str
    ) -> VerifiedIndexSuggestion:
        return VerifiedIndexSuggestion(
            **suggestion.model_dump(),
            validation=ValidationResult(
                improved=False,
                original_cost=original_cost,
                new_cost=0.0,
                improvement_factor=1.0,
                error=error,
            ),
        )
