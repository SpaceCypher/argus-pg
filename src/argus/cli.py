import argparse
import asyncio
import logging
import sys
from pathlib import Path

from argus.config import ArgusConfig, ConfigurationError, load_config
from argus.core.analyzer import Analyzer
from argus.core.brain import Brain
from argus.core.database import PsycopgReadAdapter
from argus.core.decision_engine import DecisionEngine
from argus.core.docker_sandbox import DockerSandbox
from argus.core.gemini_brain import GeminiBrain
from argus.core.heuristic_brain import HeuristicBrain
from argus.core.observer import Observer
from argus.domain.plans import ExplainPlan
from argus.domain.query import SqlStatement

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_brain(config: ArgusConfig) -> Brain:
    if config.brain.provider == "gemini":
        key = config.brain.gemini.api_key
        return GeminiBrain(api_key=key, model_name=config.brain.gemini.model)
    return HeuristicBrain()


async def run_audit(args: argparse.Namespace) -> None:
    try:
        config = load_config(args.config)
        logger.debug("Loaded configuration for audit")
    except ConfigurationError as e:
        logger.error(f"Configuration validation failed: {e}")
        sys.exit(1)

    print(f"🔍 Analyzing top {args.limit} slow queries...")
    print(f"Target DB: {config.database.dsn}")

    try:
        async with PsycopgReadAdapter(config.database.dsn) as db:
            observer = Observer(db)
            queries = await observer.fetch_top_queries(limit=args.limit)

            if not queries:
                print("No queries found in pg_stat_statements.")
                return

            headers = (
                f"\n{'Fingerprint':<16} | {'Calls':<8} | {'Mean(ms)':<10} | "
                f"{'Node Type':<15} | {'Cost':<10}"
            )
            print(headers)
            print("-" * 75)

            for query_obj, stats in queries:
                try:
                    # Run EXPLAIN (FORMAT JSON)
                    explain_sql = f"EXPLAIN (FORMAT JSON, COSTS TRUE, GENERIC_PLAN TRUE) {query_obj.raw_query}"

                    result = await db.fetch_one(explain_sql)
                    if not result:
                        logger.warning("Empty explain result")
                        continue

                    # result[0] is the JSON plan object
                    # Handle result type
                    plan_data = result[0] if isinstance(result, list) else result[0]

                    # Parse
                    plan = ExplainPlan(plan=plan_data[0]["Plan"])
                    analyzer = Analyzer(plan)

                    # Insights
                    scan_nodes = analyzer.find_nodes("Seq Scan")
                    top_node = (
                        scan_nodes[0].node_type if scan_nodes else plan.plan.node_type
                    )
                    cost = analyzer.get_total_cost()

                    # Print formatted row
                    fingerprint = query_obj.query_id[:16] if query_obj.query_id else "N/A"
                    mean_time = f"{stats.mean_exec_time:.2f}"
                    row = (
                        f"{fingerprint:<16} | {stats.calls:<8} | {mean_time:<10} | "
                        f"{top_node:<15} | {cost:<10.2f}"
                    )
                    print(row)

                except Exception as e:
                    logger.warning(f"Failed to analyze query {query_obj.query_id}: {e}")

    except Exception as e:
        logger.error(f"Audit failed: {e}")
        sys.exit(1)


async def run_check(args: argparse.Namespace) -> None:
    try:
        config = load_config(args.config)
        logger.debug("Loaded configuration for check")
    except ConfigurationError as e:
        logger.error(f"Configuration validation failed: {e}")
        sys.exit(1)

    query_path = Path(args.query_file)
    if not query_path.exists():
        logger.error(f"Query file not found: {query_path}")
        sys.exit(1)

    raw_sql = query_path.read_text().strip()
    if not raw_sql:
        logger.error("Query file is empty")
        sys.exit(1)

    print(f"🔍 Checking query from {args.query_file}...")
    print(f"Brain: {config.brain.provider}")

    try:
        # 1. Analyze
        # We need to run EXPLAIN against the DB to get the plan for the Brain.
        # Check command implies we have access to the DB.
        async with PsycopgReadAdapter(config.database.dsn) as db:
            explain_sql = f"EXPLAIN (FORMAT JSON, COSTS TRUE, GENERIC_PLAN TRUE) {raw_sql}"
            result = await db.fetch_one(explain_sql)
            if not result:
                logger.error("Could not explain query.")
                return
            plan_data = result[0] if isinstance(result, list) else result[0]
            plan = ExplainPlan(plan=plan_data[0]["Plan"])

        # 2. Brain
        brain = get_brain(config)
        # Mocking SqlStatement since we don't have stats for this specific single query necessarily
        # or we accept it doesn't matter for the Brain, just needs text.
        # But `propose_indexes` takes `SqlStatement` which has stats.
        # We'll construct a dummy SqlStatement wrapping the raw query.
        # The Brain only uses `raw_query` anyway.
        query_obj = SqlStatement(
            query_id="check_manual",
            raw_query=raw_sql,
            calls=1,
            total_exec_time=0.0,
            rows=0,
            plans=[],
        )
        suggestions = await brain.propose_indexes(query_obj, plan)

        if not suggestions:
            print("No indexes suggested by the Brain.")
            return

        print(f"🧠 Brain proposed {len(suggestions)} indexes. Validating in Sandbox...")

        # 3. Decision Engine (Validation)
        # Defines how to create a sandbox
        # 3. Decision Engine (Validation)
        # Defines how to create a sandbox
        def sandbox_factory() -> DockerSandbox:
            return DockerSandbox(config.sandbox)

        engine = DecisionEngine(sandbox_factory)
        verified = await engine.validate(query_obj, suggestions)

        # 4. Report
        print("\n=== Validation Report ===")
        for res in verified:
            status = "✅ PASS" if res.validation.improved else "❌ FAIL"
            factor = res.validation.improvement_factor
            print(
                f"\n{status} | Improvement: {factor:.2f}x (Cost: {res.validation.original_cost} -> {res.validation.new_cost})"
            )
            print(f"Index: {res.definition.inferred_name}")
            if res.migration:
                print(f"DDL:\n{res.migration.up_sql}")
            else:
                print("DDL: (Available in IndexDefinition, migration plan not generated)")
            if res.validation.error:
                print(f"Error: {res.validation.error}")

    except Exception as e:
        logger.error(f"Check failed: {e}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Argus-PG: PostgreSQL Index Advisor & Validator"
    )

    # Global arguments
    parser.add_argument(
        "--config", type=str, help="Path to configuration file (default: argus.toml)"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: Audit
    parser_audit = subparsers.add_parser(
        "audit", help="Analyze query logs and suggest indexes"
    )
    # Placeholder args for audit
    parser_audit.add_argument(
        "--limit", type=int, default=10, help="Analyze top N queries"
    )

    # Command: Check
    parser_check = subparsers.add_parser(
        "check", help="Validate a specific query or existing index suggestion"
    )
    parser_check.add_argument(
        "query_file", type=str, help="Path to file containing SQL query"
    )

    # Command: Watch
    parser_watch = subparsers.add_parser(
        "watch", help="Real-time monitoring of queries"
    )
    parser_watch.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Polling interval in seconds (default: 60)",
    )

    args = parser.parse_args()

    # Handle Logging Level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Dispatch to async logic
    if args.command == "audit":
        asyncio.run(run_audit(args))

    elif args.command == "check":
        asyncio.run(run_check(args))

    elif args.command == "watch":
        asyncio.run(run_watch(args))


async def run_watch(args: argparse.Namespace) -> None:
    try:
        config = load_config(args.config)
        logger.debug("Loaded configuration for watch")
    except ConfigurationError as e:
        logger.error(f"Configuration validation failed: {e}")
        sys.exit(1)

    print(f"👀 Watching DB: {config.database.dsn}")
    print(f"Poll Interval: {args.interval}s")
    print("Press Ctrl+C to stop.")

    seen_queries: set[str] = set()
    brain = get_brain(config)

    # Sandbox Factory
    def sandbox_factory() -> DockerSandbox:
        return DockerSandbox(
            image=config.sandbox.image,
            cleanup=config.sandbox.cleanup,
        )

    engine = DecisionEngine(sandbox_factory)

    try:
        async with PsycopgReadAdapter(config.database.dsn) as db:
            observer = Observer(db)
            while True:
                try:
                    # 1. Fetch Queries
                    queries_with_stats = await observer.fetch_top_queries(limit=10)
                    new_queries = [
                        (q, s)
                        for q, s in queries_with_stats
                        if q.query_id and q.query_id not in seen_queries
                    ]

                    if not new_queries:
                        logger.debug("No new queries found.")

                    for query_obj, stats in new_queries:
                        if not query_obj.query_id:
                            continue

                        print(f"\n🔎 Analyzing new query: {query_obj.query_id[:8]}...")
                        seen_queries.add(query_obj.query_id)

                        # 2. Explain
                        explain_sql = (
                            f"EXPLAIN (FORMAT JSON, COSTS TRUE, GENERIC_PLAN TRUE) {query_obj.raw_query}"
                        )
                        result = await db.fetch_one(explain_sql)
                        if not result:
                            logger.warn(f"Empty explain for {query.query_id}")
                            continue
                        plan_data = result[0] if isinstance(result, list) else result[0]
                        plan = ExplainPlan(plan=plan_data[0]["Plan"])

                        # 3. Brain
                        suggestions = await brain.propose_indexes(query_obj, plan)
                        if not suggestions:
                            print("  Examples suggestions: None")
                            continue

                        print(
                            f"  🧠 Found {len(suggestions)} suggestions. Validating..."
                        )

                        # 4. Validate
                        verified = await engine.validate(query_obj, suggestions)

                        # 5. Report
                        for res in verified:
                            if res.validation.improved:
                                print(
                                    f"  ✅ PASS | {res.definition.inferred_name} | "
                                    f"{res.validation.improvement_factor:.2f}x speedup"
                                )
                                print(f"  DDL: {res.migration_sql}")
                            else:
                                print(
                                    f"  ❌ FAIL | {res.definition.inferred_name} | "
                                    f"No improvement or error"
                                )

                    # Wait for next tick
                    await asyncio.sleep(args.interval)

                except Exception as e:
                    logger.error(f"Error in watch loop: {e}")
                    await asyncio.sleep(args.interval)

    except asyncio.CancelledError:
        print("\nStopping watch...")
    except KeyboardInterrupt:
        print("\nStopping watch...")
    except Exception as e:
        logger.error(f"Watch failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
