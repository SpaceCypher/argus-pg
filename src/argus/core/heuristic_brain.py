import re

from argus.core.analyzer import Analyzer
from argus.core.brain import Brain
from argus.domain.index import IndexDefinition, IndexSuggestion
from argus.domain.plans import ExplainPlan
from argus.domain.query import SqlStatement


class HeuristicBrain(Brain):
    """
    Optimizes queries using static rules without LLM intervention.
    Primary heuristic: Detect Seq Scans with filters and suggest indexes on columns.
    """

    # Regex to extract identifiers from a filter string.
    # Excludes typical SQL keywords by relying on lower casing later.
    # We can't easily exclude keywords without a list.
    # For a heuristic V1, we accept some noise.
    _IDENTIFIER_PATTERN = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b")

    # Common SQL keywords to ignore found in filters
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
    }

    async def propose_indexes(
        self, query: SqlStatement, plan: ExplainPlan
    ) -> list[IndexSuggestion]:
        suggestions: list[IndexSuggestion] = []
        analyzer = Analyzer(plan)

        # 1. Find all Seq Scan nodes
        seq_scans = analyzer.find_nodes("Seq Scan")

        for node in seq_scans:
            if not node.filter_condition:
                continue

            # 2. Extract potential columns from filter
            columns = self._extract_columns(node.filter_condition)

            if not columns:
                continue

            # 3. Create suggestion
            # We assume the relation_name is the table name.
            if not node.relation_name:
                continue

            suggestion = IndexSuggestion(
                target_query_id=query.query_id,
                definition=IndexDefinition(
                    table_name=node.relation_name,
                    schema_name=node.schema_name or "public",
                    columns=list(columns),
                    method="btree",
                ),
                reasoning=(
                    f"Found Seq Scan on '{node.relation_name}' "
                    f"with filter: {node.filter_condition}"
                ),
            )
            suggestions.append(suggestion)

        return suggestions

    def _extract_columns(self, filter_str: str) -> set[str]:
        """
        Extracts potential column names from a filter string.
        """
        matches = self._IDENTIFIER_PATTERN.findall(filter_str)
        columns = set()

        for match in matches:
            candidate = match.lower()
            # Filter out numeric literals (regex handles start char, checking safety)
            if candidate.isdigit():
                continue
            if candidate in self._IGNORED_KEYWORDS:
                continue
            # Simple heuristic: ignore short tokens likely to be aliases if not cols
            # But 'id' is short. So keep all.
            columns.add(candidate)

        return columns
