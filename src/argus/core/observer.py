from argus.core.database import DatabaseAdapter
from argus.domain.query import PgStatStats, SqlStatement


class Observer:
    """
    Observes a target database to extract high-load queries.
    Uses a safe, read-only DatabaseAdapter.
    """

    def __init__(self, adapter: DatabaseAdapter):
        self._adapter = adapter

    async def fetch_top_queries(
        self, limit: int = 10
    ) -> list[tuple[SqlStatement, PgStatStats]]:
        """
        Fetch top queries by total execution time from pg_stat_statements.
        Filters for queries in the current database context.
        """
        # We assume the adapter is already connected (entered via context manager)
        # or will be managed by the caller. The Observer itself is a logic component,
        # not a connection manager, though it depends on one.

        # Query: join pg_stat_statements with pg_database to filter by current DB.
        # This prevents picking up stats from other DBs if the extension is shared.
        sql = """
            SELECT 
                pss.query,
                pss.calls,
                pss.total_exec_time,
                pss.rows
            FROM pg_stat_statements pss
            JOIN pg_database db ON pss.dbid = db.oid
            WHERE db.datname = current_database()
            ORDER BY pss.total_exec_time DESC
            LIMIT %s
        """

        # Note: Psycopg v3 uses %s for placeholders
        rows = await self._adapter.fetch_all(sql, [limit])

        results: list[tuple[SqlStatement, PgStatStats]] = []
        for row in rows:
            # row is a tuple/list: (query, calls, total_exec_time, rows)
            # Depending on row factory, usually tuple.
            raw_query, calls, total_time, row_count = row

            # Skip empty queries if any
            if not raw_query or not raw_query.strip():
                continue

            try:
                statement = SqlStatement(raw_query=raw_query)
                stats = PgStatStats(
                    calls=calls, total_exec_time=float(total_time), rows=row_count
                )
                results.append((statement, stats))
            except ValueError:
                # Skip invalid statements (validation error in model)
                continue

        return results
