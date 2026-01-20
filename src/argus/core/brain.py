from abc import ABC, abstractmethod

from argus.domain.index import IndexSuggestion
from argus.domain.plans import ExplainPlan
from argus.domain.query import SqlStatement


class Brain(ABC):
    """
    Abstract interface for component responsible for generating index suggestions.
    Implementations may be heuristic-based or LLM-based.
    """

    @abstractmethod
    async def propose_indexes(
        self, query: SqlStatement, plan: ExplainPlan
    ) -> list[IndexSuggestion]:
        """
        Analyze the query and its execution plan to propose optimizing indexes.

        Args:
            query: The target SQL query details.
            plan: The analyzed execution plan (with costs and node types).

        Returns:
            A list of IndexSuggestion objects. Returns empty list if no improvements.
        """
        pass
