from pydantic import BaseModel, ConfigDict, Field


class PlanNode(BaseModel):
    """
    Recursive structure representing a node in a Postgres EXPLAIN (FORMAT JSON) tree.
    """

    node_type: str = Field(..., alias="Node Type")
    relation_name: str | None = Field(None, alias="Relation Name")
    schema_name: str | None = Field(None, alias="Schema")
    alias: str | None = Field(None, alias="Alias")
    index_name: str | None = Field(None, alias="Index Name")
    filter_condition: str | None = Field(None, alias="Filter")

    startup_cost: float = Field(..., alias="Startup Cost")
    total_cost: float = Field(..., alias="Total Cost")
    plan_rows: int = Field(..., alias="Plan Rows")
    plan_width: int = Field(..., alias="Plan Width")

    # Execution stats (present if ANALYZE was used)
    actual_startup_time: float | None = Field(None, alias="Actual Startup Time")
    actual_total_time: float | None = Field(None, alias="Actual Total Time")
    actual_rows: int | None = Field(None, alias="Actual Rows")
    actual_loops: int | None = Field(None, alias="Actual Loops")

    # Recursive children
    plans: list["PlanNode"] = Field(default_factory=list, alias="Plans")

    model_config = ConfigDict(populate_by_name=True)


class ExplainPlan(BaseModel):
    """
    Root container for a parsed EXPLAIN plan.
    """

    plan: PlanNode = Field(..., alias="Plan")
    planning_time: float | None = Field(None, alias="Planning Time")
    execution_time: float | None = Field(None, alias="Execution Time")

    model_config = ConfigDict(populate_by_name=True)
