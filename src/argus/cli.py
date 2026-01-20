import argparse
import logging
import sys

from argus.config import ConfigurationError, load_config

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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

    try:
        config = load_config(args.config)
        logger.debug(f"Loaded configuration: {config}")
    except ConfigurationError as e:
        logger.error(f"Configuration validation failed: {e}")
        sys.exit(1)

    # Placeholder Dispatch
    if args.command == "audit":
        print(f"Audit command invoked. Limit: {args.limit}")
        print("Note: This is a skeleton. functionality coming in Task 5.3")

    elif args.command == "check":
        print(f"Check command invoked. Query File: {args.query_file}")
        print("Note: This is a skeleton. functionality coming in Task 5.4")

    elif args.command == "watch":
        print("Watch command invoked.")
        print("Note: This is a skeleton. functionality coming in Task 5.5")


if __name__ == "__main__":
    main()
