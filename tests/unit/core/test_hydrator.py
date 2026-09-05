from argus.core.hydrator import DataHydrator
from argus.core.schema import ColumnMetadata, TableMetadata


def test_data_hydrator_predicate_extraction():
    sql = "SELECT * FROM orders WHERE status = 'PENDING' AND user_id = 42"
    predicates = DataHydrator.extract_predicates_from_query(sql)

    assert predicates.get("status") == "PENDING"
    assert predicates.get("user_id") == "42"


def test_data_hydrator_sql_generation():
    hydrator = DataHydrator()
    table = TableMetadata(table_name="users", schema_name="public")
    table.columns = [
        ColumnMetadata(
            name="id",
            data_type="integer",
            udt_name="int4",
            is_nullable=False,
            is_primary_key=True,
        ),
        ColumnMetadata(
            name="email", data_type="text", udt_name="text", is_nullable=False
        ),
        ColumnMetadata(
            name="created_at",
            data_type="timestamp",
            udt_name="timestamp",
            is_nullable=False,
        ),
    ]

    sql = hydrator.generate_table_hydration_sql(
        table_meta=table,
        row_count=5000,
        query_predicates={"email": "user_42000@example.com"},
    )

    assert 'INSERT INTO "public"."users"' in sql
    assert "generate_series(1, 5000)" in sql
    assert "user_42000@example.com" in sql
    assert "ANALYZE" in sql
