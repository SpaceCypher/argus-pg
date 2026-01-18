import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Constrain index methods to typical Postgres types
IndexMethod = Literal["btree", "gin", "gist", "hash", "brin"]


class IndexDefinition(BaseModel):
    """
    Represents a proposed Postgres index.
    """

    table_name: str = Field(..., description="Target table name (e.g. 'users')")
    schema_name: str = Field("public", description="Schema name")
    columns: list[str] = Field(
        ..., min_length=1, description="List of columns/expressions"
    )
    method: IndexMethod = Field("btree", description="Index method")
    unique: bool = Field(False, description="Is this a UNIQUE index?")

    @property
    def inferred_name(self) -> str:
        """
        Generates a standard index name: idx_<table>_<columns>
        """
        # Simplistic generation. Real impl might shorten long names.
        clean_cols = "_".join(
            c.replace("(", "").replace(")", "").replace(" ", "") for c in self.columns
        )
        name = f"idx_{self.table_name}_{clean_cols}"
        return name[:63].lower()  # Postgres constraint

    @field_validator("table_name", "schema_name")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(f"Identifier {v} contains invalid characters")
        return v.lower()


class MigrationPlan(BaseModel):
    """
    Represents the concrete DDL to apply this index locally or in prod.
    """

    up_sql: str = Field(
        ..., description="The DDL to create the index (preferably CONCURRENTLY)"
    )
    down_sql: str = Field(..., description="The DDL to drop the index")
    transactional: bool = Field(
        False,
        description="Whether this DDL runs in a transaction (CONCURRENTLY cannot)",
    )


class IndexSuggestion(BaseModel):
    """
    Links a candidate index to the query it intends to optimize.
    """

    target_query_id: str = Field(..., description="Reference to Query.query_id")
    definition: IndexDefinition
    reasoning: str = Field(
        ..., description="Why this index is suggested (LLM or heuristic)"
    )
    migration: MigrationPlan | None = None  # Computed later
