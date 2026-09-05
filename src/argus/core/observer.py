import logging

from argus.core.database import DatabaseAdapter
from argus.core.schema import SchemaExtractor
from argus.domain.query import PgStatStats, SqlStatement

logger = logging.getLogger(__name__)


class Observer:
    """
    Observes a target database to extract high-load queries.
    Uses a safe, read-only DatabaseAdapter.
    """

    def __init__(self, adapter: DatabaseAdapter, min_table_pages: int = 10):
        self._adapter = adapter
        self.min_table_pages = min_table_pages

    async def fetch_top_queries(
        self, limit: int = 10, filter_small_tables: bool = False
    ) -> list[tuple[SqlStatement, PgStatStats]]:
        """
        Fetch top queries by total execution time from pg_stat_statements.
        Filters for queries in the current database context.
        Optionally filters out queries running strictly on small tables (< min_table_pages).
        """
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

        rows = await self._adapter.fetch_all(sql, [limit])

        results: list[tuple[SqlStatement, PgStatStats]] = []
        for row in rows:
            raw_query, calls, total_time, row_count = row

            if not raw_query or not raw_query.strip():
                continue

            # Strip comments and whitespace
            import re

            cleaned_q = re.sub(r"/\*.*?\*/", "", raw_query, flags=re.DOTALL)
            cleaned_q = re.sub(r"--[^\n]*", "", cleaned_q).strip()
            lower_q = cleaned_q.lower()
            if not lower_q:
                continue

            # Only monitor optimizable data statements
            if not any(
                lower_q.startswith(prefix)
                for prefix in ("select", "with", "insert", "update", "delete")
            ):
                continue

            # Ignore internal pg_stat_statements or catalog polling queries
            if (
                "pg_stat_statements" in lower_q
                or "pg_catalog" in lower_q
                or "information_schema" in lower_q
            ):
                continue

            try:
                statement = SqlStatement(raw_query=raw_query)
                stats = PgStatStats(
                    calls=calls, total_exec_time=float(total_time), rows=row_count
                )

                if filter_small_tables and self.min_table_pages > 0:
                    tables = SchemaExtractor.extract_table_names(raw_query)
                    if tables:
                        is_large = await self._has_large_table(tables)
                        if not is_large:
                            logger.debug(
                                f"Skipping query on small tables: {raw_query[:50]}"
                            )
                            continue

                results.append((statement, stats))
            except ValueError:
                continue

        return results

    async def _has_large_table(self, table_names: list[str]) -> bool:
        """
        Checks pg_class to see if at least one table in the list exceeds min_table_pages.
        """
        check_sql = """
            SELECT c.relname, c.relpages, c.reltuples
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = ANY(%s)
        """
        try:
            rows = await self._adapter.fetch_all(check_sql, [table_names])
            if not rows:
                return True  # If not found in catalog, don't drop conservatively
            return any(
                (r[1] or 0) >= self.min_table_pages or (r[2] or 0) >= 1000 for r in rows
            )
        except Exception as e:
            logger.debug(f"Failed to check table sizes in pg_class: {e}")
            return True
