from pydantic import BaseModel, ConfigDict, Field


class PlanNode(BaseModel):
    """
    Recursive structure representing a node in a Postgres EXPLAIN (FORMAT JSON) tree.
    """

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    node_type: str = Field(..., validation_alias="Node Type")
    relation_name: str | None = Field(None, validation_alias="Relation Name")
    schema_name: str | None = Field(None, validation_alias="Schema")
    alias: str | None = Field(None, validation_alias="Alias")
    index_name: str | None = Field(None, validation_alias="Index Name")
    filter_condition: str | None = Field(None, validation_alias="Filter")

    startup_cost: float = Field(0.0, validation_alias="Startup Cost")
    total_cost: float = Field(0.0, validation_alias="Total Cost")
    plan_rows: int = Field(0, validation_alias="Plan Rows")
    plan_width: int = Field(0, validation_alias="Plan Width")

    # Execution stats (present if ANALYZE was used)
    actual_startup_time: float | None = Field(
        None, validation_alias="Actual Startup Time"
    )
    actual_total_time: float | None = Field(None, validation_alias="Actual Total Time")
    actual_rows: int | None = Field(None, validation_alias="Actual Rows")
    actual_loops: int | None = Field(None, validation_alias="Actual Loops")

    # Recursive children
    plans: list["PlanNode"] = Field(default_factory=list, validation_alias="Plans")


class ExplainPlan(BaseModel):
    """
    Root container for a parsed EXPLAIN plan.
    """

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    plan: PlanNode = Field(..., validation_alias="Plan")
    planning_time: float | None = Field(None, validation_alias="Planning Time")
    execution_time: float | None = Field(None, validation_alias="Execution Time")
