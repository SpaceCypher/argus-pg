import logging

import sqlglot
from sqlglot import exp

from argus.core.database import DatabaseAdapter

logger = logging.getLogger(__name__)


class ColumnMetadata:
    def __init__(
        self,
        name: str,
        data_type: str,
        udt_name: str,
        is_nullable: bool,
        default_value: str | None = None,
        is_primary_key: bool = False,
    ):
        self.name = name
        self.data_type = data_type.lower()
        self.udt_name = udt_name.lower()
        self.is_nullable = is_nullable
        self.default_value = default_value
        self.is_primary_key = is_primary_key

    def to_column_def(self) -> str:
        type_str = self.udt_name
        if type_str in ("varchar", "character varying"):
            type_str = "text"
        elif type_str in ("int4", "integer"):
            type_str = "int"
        elif type_str in ("int8", "bigint"):
            type_str = "bigint"
        elif type_str in ("int2", "smallint"):
            type_str = "smallint"
        elif type_str in ("bool", "boolean"):
            type_str = "boolean"
        elif type_str in (
            "timestamp",
            "timestamptz",
            "timestamp without time zone",
            "timestamp with time zone",
        ):
            type_str = "timestamp"

        if self.is_primary_key:
            if "serial" in type_str or (
                self.default_value and "nextval" in self.default_value
            ):
                if type_str in ("bigint", "int8"):
                    return f'"{self.name}" bigserial PRIMARY KEY'
                return f'"{self.name}" serial PRIMARY KEY'
            return f'"{self.name}" {type_str} PRIMARY KEY'

        nullable_str = "" if self.is_nullable else " NOT NULL"
        default_str = f" DEFAULT {self.default_value}" if self.default_value else ""
        return f'"{self.name}" {type_str}{default_str}{nullable_str}'.strip()


class TableMetadata:
    def __init__(self, table_name: str, schema_name: str = "public"):
        self.table_name = table_name
        self.schema_name = schema_name
        self.columns: list[ColumnMetadata] = []
        self.enums: dict[str, list[str]] = {}

    def to_ddl(self) -> str:
        ddl_parts: list[str] = []
        for enum_name, enum_values in self.enums.items():
            vals = ", ".join(f"'{v}'" for v in enum_values)
            ddl_parts.append(
                f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}') "
                f"THEN CREATE TYPE {enum_name} AS ENUM ({vals}); END IF; END $$;"
            )

        col_defs = ",\n    ".join(col.to_column_def() for col in self.columns)
        ddl_parts.append(
            f'CREATE TABLE IF NOT EXISTS "{self.schema_name}"."{self.table_name}" (\n    {col_defs}\n);'
        )
        return "\n".join(ddl_parts)


class SchemaExtractor:
    """
    Introspects PostgreSQL catalogs to extract schema definitions, column types,
    and constraints for targeted tables.
    """

    def __init__(self, db_adapter: DatabaseAdapter):
        self._db = db_adapter

    @staticmethod
    def extract_table_names(sql_query: str) -> list[str]:
        """
        Uses sqlglot AST to extract all table names referenced in a SQL query.
        """
        table_names: set[str] = set()
        try:
            parsed = sqlglot.parse_one(sql_query, read="postgres")
            for table in parsed.find_all(exp.Table):
                if table.name:
                    table_names.add(table.name.lower())
        except Exception as e:
            logger.warning(f"sqlglot failed to parse table names from query: {e}")
            import re

            matches = re.findall(
                r"\b(?:from|join|into|update)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                sql_query,
                re.IGNORECASE,
            )
            for m in matches:
                table_names.add(m.lower())

        return list(table_names)

    async def extract_table_schema(
        self, table_name: str, schema_name: str = "public"
    ) -> TableMetadata | None:
        """
        Extracts column definitions and constraints for a specific table.
        """
        table_meta = TableMetadata(table_name=table_name, schema_name=schema_name)

        # 1. Fetch Columns
        cols_query = """
            SELECT 
                column_name, 
                data_type, 
                udt_name, 
                is_nullable, 
                column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        rows = await self._db.fetch_all(cols_query, [schema_name, table_name])
        if not rows:
            logger.warning(
                f"Table '{schema_name}.{table_name}' not found in information_schema."
            )
            return None

        # 2. Fetch Primary Keys
        pk_query = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
        """
        pk_rows = await self._db.fetch_all(pk_query, [schema_name, table_name])
        pk_columns = {r[0] for r in pk_rows} if pk_rows else set()

        for col_name, data_type, udt_name, is_nullable, col_default in rows:
            is_pk = col_name in pk_columns
            table_meta.columns.append(
                ColumnMetadata(
                    name=col_name,
                    data_type=data_type,
                    udt_name=udt_name,
                    is_nullable=(is_nullable.upper() == "YES"),
                    default_value=col_default,
                    is_primary_key=is_pk,
                )
            )

        # 3. Check for ENUM types
        enum_query = """
            SELECT t.typname, e.enumlabel
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = %s
            ORDER BY t.typname, e.enumsortorder
        """
        try:
            enum_rows = await self._db.fetch_all(enum_query, [schema_name])
            if enum_rows:
                for typname, enumlabel in enum_rows:
                    if typname not in table_meta.enums:
                        table_meta.enums[typname] = []
                    table_meta.enums[typname].append(enumlabel)
        except Exception as e:
            logger.debug(f"Enum extraction skipped/failed: {e}")

        return table_meta

    async def extract_schema_ddl(
        self, table_names: list[str], schema_name: str = "public"
    ) -> str:
        """
        Extracts combined DDL for all given tables.
        """
        ddl_parts: list[str] = []
        for tbl in table_names:
            meta = await self.extract_table_schema(tbl, schema_name)
            if meta:
                ddl_parts.append(meta.to_ddl())

        return "\n\n".join(ddl_parts)
