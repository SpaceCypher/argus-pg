import logging
import re

from faker import Faker

from argus.core.schema import ColumnMetadata, TableMetadata

logger = logging.getLogger(__name__)


class DataHydrator:
    """
    Generates synthetic data for database schemas in the sandbox to replicate
    production-like statistical cardinality and selectivity for the query planner.
    """

    def __init__(self, faker_seed: int = 42):
        self._faker = Faker()
        Faker.seed(faker_seed)

    @staticmethod
    def extract_predicates_from_query(sql_query: str) -> dict[str, str]:
        """
        Extracts column -> value equality literals from query WHERE conditions
        e.g., status = 'PENDING', email = 'user_42000@example.com'.
        """
        predicates: dict[str, str] = {}
        # Match col = 'val' or col = 123
        pattern = re.compile(
            r"""\b([a-zA-Z0-9_]+)\s*=\s*(?:'([^']*)'|(\d+\.?\d*))""",
            re.IGNORECASE,
        )
        for match in pattern.finditer(sql_query):
            col_name = match.group(1).lower()
            str_val = match.group(2)
            num_val = match.group(3)
            val = str_val if str_val is not None else num_val
            predicates[col_name] = val
        return predicates

    def generate_table_hydration_sql(
        self,
        table_meta: TableMetadata,
        row_count: int = 20000,
        query_predicates: dict[str, str] | None = None,
    ) -> str:
        """
        Generates fast PostgreSQL set-based synthetic data insertion statements
        with realistic cardinality distribution.
        """
        if not table_meta.columns:
            return ""

        query_predicates = query_predicates or {}
        col_names: list[str] = []
        col_exprs: list[str] = []

        for col in table_meta.columns:
            col_names.append(f'"{col.name}"')
            expr = self._build_column_generator_expression(
                col=col,
                table_meta=table_meta,
                target_value=query_predicates.get(col.name.lower()),
            )
            col_exprs.append(expr)

        if not col_names:
            return ""

        cols_joined = ", ".join(col_names)
        exprs_joined = ",\n        ".join(col_exprs)
        full_table = f'"{table_meta.schema_name}"."{table_meta.table_name}"'

        sql = f"""
INSERT INTO {full_table} ({cols_joined})
SELECT
        {exprs_joined}
FROM generate_series(1, {row_count}) AS i;

ANALYZE {full_table};
""".strip()

        return sql

    def _build_column_generator_expression(
        self,
        col: ColumnMetadata,
        table_meta: TableMetadata,
        target_value: str | None = None,
    ) -> str:
        cname = col.name.lower()
        udt = col.udt_name.lower()

        # Handle ENUM types
        if udt in table_meta.enums:
            enum_vals = table_meta.enums[udt]
            if target_value and target_value in enum_vals:
                # 10% target value, 90% random
                other_vals = [v for v in enum_vals if v != target_value] or [
                    target_value
                ]
                arr_sql = (
                    "ARRAY[" + ", ".join(f"'{v}'::{udt}" for v in other_vals) + "]"
                )
                return (
                    f"CASE WHEN random() < 0.1 THEN '{target_value}'::{udt} "
                    f"ELSE ({arr_sql})[floor(random() * {len(other_vals)} + 1)::int] END"
                )
            else:
                arr_sql = "ARRAY[" + ", ".join(f"'{v}'::{udt}" for v in enum_vals) + "]"
                return f"({arr_sql})[floor(random() * {len(enum_vals)} + 1)::int]"

        # Handle specific column patterns by name
        if "email" in cname:
            if target_value and "@" in target_value:
                return f"CASE WHEN i = 42 THEN '{target_value}' ELSE 'user_' || i || '@example.com' END"
            return "'user_' || i || '@example.com'"

        if "status" in cname or "state" in cname:
            if target_value:
                return f"CASE WHEN random() < 0.15 THEN '{target_value}' ELSE 'STATUS_' || (floor(random() * 5)::int) END"
            return "'STATUS_' || (floor(random() * 5)::int)"

        if "created_at" in cname or "updated_at" in cname or "timestamp" in udt:
            return "now() - (i * interval '1 minute')"

        if "date" in udt:
            return "CURRENT_DATE - (floor(random() * 365)::int)"

        if udt in ("bool", "boolean"):
            if target_value:
                bool_val = target_value.lower() in ("true", "t", "1")
                return f"CASE WHEN random() < 0.2 THEN {str(bool_val).upper()} ELSE {str(not bool_val).upper()} END"
            return "(random() > 0.5)"

        if udt in ("int2", "int4", "int8", "smallint", "integer", "bigint"):
            if col.is_primary_key:
                return "i"
            if target_value and target_value.isdigit():
                return f"CASE WHEN i = 42 THEN {target_value} ELSE floor(random() * 100000)::int END"
            return "floor(random() * 10000)::int"

        if udt in ("numeric", "float4", "float8", "decimal"):
            if target_value:
                try:
                    num = float(target_value)
                    return f"CASE WHEN i = 42 THEN {num} ELSE (random() * 1000)::numeric(10, 2) END"
                except ValueError:
                    pass
            return "(random() * 1000)::numeric(10, 2)"

        if udt in ("uuid",):
            return "gen_random_uuid()"

        # Fallback text/varchar
        if target_value:
            return f"CASE WHEN i = 42 THEN '{target_value}' ELSE 'val_' || md5(i::text) END"

        return "'val_' || md5(i::text)"
