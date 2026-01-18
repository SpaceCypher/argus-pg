from abc import ABC, abstractmethod
from typing import Any, Self

from argus.domain.index import IndexDefinition
from argus.domain.query import PgStatStats, SqlStatement


class Sandbox(ABC):
    """
    Abstract contract for a deterministic index validation environment.
    Implementations (Adapters) must handle infrastructure (Docker, connection pools).
    """

    @abstractmethod
    async def __aenter__(self) -> Self:
        """
        Initialize the sandbox environment (e.g. provision container, wait for health).
        """
        return self

    @abstractmethod
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Teardown the sandbox environment (e.g. stop/remove container).
        """
        pass

    @abstractmethod
    async def reset_metrics(self) -> None:
        """
        Clear any execution statistics to ensure a clean measurement baseline.
        """
        pass

    @abstractmethod
    async def run_query(self, query: SqlStatement) -> PgStatStats:
        """
        Execute a query and return structured performance metrics.
        Must allow exception to propagate if execution fails destructively.
        """
        pass

    @abstractmethod
    async def apply_index(self, index: IndexDefinition) -> None:
        """
        Apply an index definition to the sandbox environment.
        """
        pass
