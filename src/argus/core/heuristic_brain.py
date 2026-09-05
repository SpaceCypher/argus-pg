import logging
import re

import sqlglot
from sqlglot import exp

from argus.core.analyzer import Analyzer
from argus.core.brain import Brain
from argus.domain.index import IndexDefinition, IndexSuggestion
from argus.domain.plans import ExplainPlan
from argus.domain.query import SqlStatement

logger = logging.getLogger(__name__)


class HeuristicBrain(Brain):
    """
    Optimizes queries using static rules and AST analysis without LLM intervention.
    Primary heuristic: Detect Seq Scans with filters and suggest indexes on filtering and join columns.
    """

    _IDENTIFIER_PATTERN = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b")

    _IGNORED_KEYWORDS = {
        "and",
        "or",
        "not",
        "in",
        "is",
        "null",
        "true",
        "false",
        "like",
        "ilike",
        "any",
        "all",
        "some",
        "between",
        "distinct",
        "cast",
        "coalesce",
        "lower",
        "upper",
        "length",
        "text",
    }

    async def propose_indexes(
        self, query: SqlStatement, plan: ExplainPlan
    ) -> list[IndexSuggestion]:
        suggestions: list[IndexSuggestion] = []
        analyzer = Analyzer(plan)

        # 1. Find all Seq Scan nodes from EXPLAIN plan
        seq_scans = analyzer.find_nodes("Seq Scan")

        # Also extract columns via sqlglot AST
        ast_columns_by_table = self._extract_ast_columns(query.raw_query)

        for node in seq_scans:
            if not node.relation_name:
                continue

            tbl_name = node.relation_name.lower()
            columns: set[str] = set()

            # Strategy A: Extract from plan filter_condition
            if node.filter_condition:
                cols_from_filter = self._extract_columns(node.filter_condition)
                columns.update(cols_from_filter)

            # Strategy B: Extract from sqlglot AST
            if tbl_name in ast_columns_by_table:
                columns.update(ast_columns_by_table[tbl_name])

            if not columns:
                continue

            # Create suggestions (single-column and composite if multiple)
            col_list = sorted(list(columns))
            suggestion = IndexSuggestion(
                target_query_id=query.query_id,
                definition=IndexDefinition(
                    table_name=node.relation_name,
                    schema_name=node.schema_name or "public",
                    columns=col_list,
                    method="btree",
                ),
                reasoning=(
                    f"Found Seq Scan on '{node.relation_name}' "
                    f"with filter: {node.filter_condition or 'predicate in query'}"
                ),
            )
            suggestions.append(suggestion)

        return suggestions

    def _extract_ast_columns(self, sql_query: str) -> dict[str, set[str]]:
        """
        Uses sqlglot AST to find columns used in WHERE predicates and JOIN conditions.
        """
        table_columns: dict[str, set[str]] = {}
        try:
            parsed = sqlglot.parse_one(sql_query, read="postgres")
            # Extract where columns
            where_clause = parsed.find(exp.Where)
            if where_clause:
                for col in where_clause.find_all(exp.Column):
                    tbl = (col.table or "").lower()
                    cname = col.name.lower()
                    if tbl:
                        table_columns.setdefault(tbl, set()).add(cname)
                    else:
                        # Assign to all from tables
                        for table in parsed.find_all(exp.Table):
                            if table.name:
                                table_columns.setdefault(table.name.lower(), set()).add(
                                    cname
                                )
        except Exception as e:
            logger.debug(f"sqlglot AST column extraction failed: {e}")

        return table_columns

    def _extract_columns(self, filter_str: str) -> set[str]:
        clean_str = self._strip_literals(filter_str)
        matches = self._IDENTIFIER_PATTERN.findall(clean_str)
        columns = set()

        for match in matches:
            candidate = match.lower()
            if candidate.isdigit() or candidate in self._IGNORED_KEYWORDS:
                continue
            columns.add(candidate)

        return columns

    def _strip_literals(self, text: str) -> str:
        return re.sub(r"'(''|[^'])*'", "", text)
