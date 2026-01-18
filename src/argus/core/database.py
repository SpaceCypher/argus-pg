from abc import ABC, abstractmethod
from typing import Any, Self

import psycopg

from argus.domain.errors import DependencyError


class DatabaseAdapter(ABC):
    """
    Abstract interface for database interactions.
    Strictly enforced as Read-Only for Observation components.
    """

    @abstractmethod
    async def __aenter__(self) -> Self:
        pass

    @abstractmethod
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    @abstractmethod
    async def fetch_all(self, query: str, params: list[Any] | None = None) -> list[Any]:
        """
        Execute a query and return all rows.
        Safe for read-only operations.
        """
        pass

    @abstractmethod
    async def fetch_one(self, query: str, params: list[Any] | None = None) -> Any:
        """
        Execute a query and return a single row.
        Safe for read-only operations.
        """
        pass


class PsycopgReadAdapter(DatabaseAdapter):
    """
    Concrete implementation using Psycopg (v3).
    Enforces READ ONLY transaction isolation level.
    """

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._conn: psycopg.AsyncConnection[Any] | None = None

    async def __aenter__(self) -> Self:
        try:
            # Connect
            self._conn = await psycopg.AsyncConnection.connect(
                self.dsn, autocommit=True
            )

            # Enforce Read-Only at the transaction/session level
            async with self._conn.cursor() as cur:
                await cur.execute(
                    "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY"
                )

            return self
        except Exception as e:
            raise DependencyError(f"Database connection failed: {e}") from e

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def fetch_all(self, query: str, params: list[Any] | None = None) -> list[Any]:
        if not self._conn:
            raise DependencyError("Connection not initialized")

        try:
            async with self._conn.cursor() as cur:
                await cur.execute(query, params)
                return await cur.fetchall()
        except Exception as e:
            raise DependencyError(f"Query failed: {e}") from e

    async def fetch_one(self, query: str, params: list[Any] | None = None) -> Any:
        if not self._conn:
            raise DependencyError("Connection not initialized")

        try:
            async with self._conn.cursor() as cur:
                await cur.execute(query, params)
                return await cur.fetchone()
        except Exception as e:
            raise DependencyError(f"Query failed: {e}") from e
