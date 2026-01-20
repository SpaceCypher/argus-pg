import argparse
import asyncio
import logging
import sys

from argus.config import ConfigurationError, load_config
from argus.core.analyzer import Analyzer
from argus.core.database import PsycopgReadAdapter
from argus.core.observer import Observer
from argus.domain.plans import ExplainPlan

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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

            for query in queries:
                try:
                    # Run EXPLAIN (FORMAT JSON)
                    explain_sql = f"EXPLAIN (FORMAT JSON, COSTS TRUE) {query.raw_query}"

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
                    fingerprint = query.query_id[:16] if query.query_id else "N/A"
                    mean_time = f"{query.mean_exec_time:.2f}"
                    row = (
                        f"{fingerprint:<16} | {query.calls:<8} | {mean_time:<10} | "
                        f"{top_node:<15} | {cost:<10.2f}"
                    )
                    print(row)

                except Exception as e:
                    logger.warning(f"Failed to analyze query {query.query_id}: {e}")

    except Exception as e:
        logger.error(f"Audit failed: {e}")
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
    subparsers.add_parser("watch", help="Real-time monitoring of queries")

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
        print(f"Check command invoked. Query File: {args.query_file}")
        print("Note: This is a skeleton. functionality coming in Task 5.4")

    elif args.command == "watch":
        print("Watch command invoked.")
        print("Note: This is a skeleton. functionality coming in Task 5.5")


if __name__ == "__main__":
    main()
