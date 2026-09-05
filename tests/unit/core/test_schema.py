from unittest.mock import AsyncMock

import pytest

from argus.core.database import DatabaseAdapter
from argus.core.schema import ColumnMetadata, SchemaExtractor, TableMetadata


def test_schema_extractor_extract_table_names():
    sql = """
        SELECT u.id, u.email, o.total
        FROM users u
        JOIN orders o ON u.id = o.user_id
        WHERE u.email = 'test@example.com'
    """
    tables = SchemaExtractor.extract_table_names(sql)
    assert "users" in tables
    assert "orders" in tables


def test_table_metadata_ddl_generation():
    table = TableMetadata(table_name="orders", schema_name="public")
    table.columns = [
        ColumnMetadata(
            name="id",
            data_type="integer",
            udt_name="int4",
            is_nullable=False,
            is_primary_key=True,
        ),
        ColumnMetadata(
            name="status", data_type="text", udt_name="text", is_nullable=False
        ),
        ColumnMetadata(
            name="amount", data_type="numeric", udt_name="numeric", is_nullable=True
        ),
    ]

    ddl = table.to_ddl()
    assert 'CREATE TABLE IF NOT EXISTS "public"."orders"' in ddl
    assert '"id" int PRIMARY KEY' in ddl
    assert '"status" text NOT NULL' in ddl
    assert '"amount" numeric' in ddl


@pytest.mark.asyncio
async def test_schema_extractor_catalog_introspection():
    mock_db = AsyncMock(spec=DatabaseAdapter)
    # Mock columns query result: (column_name, data_type, udt_name, is_nullable, column_default)
    mock_db.fetch_all.side_effect = [
        [
            ("id", "integer", "int4", "NO", "nextval('users_id_seq')"),
            ("email", "text", "text", "NO", None),
        ],
        [("id",)],  # Primary key query result
        [],  # Enum query result
    ]

    extractor = SchemaExtractor(mock_db)
    meta = await extractor.extract_table_schema("users", "public")

    assert meta is not None
    assert meta.table_name == "users"
    assert len(meta.columns) == 2
    assert meta.columns[0].is_primary_key is True
    assert meta.columns[1].name == "email"
