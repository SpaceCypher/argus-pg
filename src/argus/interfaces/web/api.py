import re
from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from argus.config import load_config
from argus.core.analyzer import Analyzer
from argus.core.brain import Brain
from argus.core.database import PsycopgReadAdapter
from argus.core.decision_engine import DecisionEngine
from argus.core.docker_sandbox import DockerSandbox, get_docker_client
from argus.core.gemini_brain import GeminiBrain
from argus.core.heuristic_brain import HeuristicBrain
from argus.core.observer import Observer
from argus.core.schema import SchemaExtractor
from argus.domain.plans import ExplainPlan
from argus.domain.query import SqlStatement
from argus.interfaces.explanation_formatter import ExplanationFormatter

router = APIRouter(prefix="/api")


def _mask_dsn(dsn: str) -> str:
    """Mask password in DSN for safe UI display."""
    return re.sub(r":([^:@]+)@", ":****@", dsn)


class CheckRequest(BaseModel):
    query: str = Field(..., description="SQL Query to analyze and optimize")
    brain_provider: str = Field("heuristic", description="'heuristic' or 'gemini'")
    gemini_api_key: str | None = None
    gemini_model: str | None = None


class ApplyRequest(BaseModel):
    sql: str = Field(..., description="CREATE INDEX SQL to execute on target database")


@router.get("/health")
async def health_check() -> dict[str, Any]:
    db_ok = False
    db_error = None
    docker_ok = False
    docker_error = None

    config = load_config()
    safe_dsn = _mask_dsn(config.database.dsn)

    # 1. Database Check
    try:
        async with PsycopgReadAdapter(config.database.dsn) as db:
            row = await db.fetch_one("SELECT 1")
            db_ok = bool(row and row[0] == 1)
    except Exception as e:
        err_msg = str(e)
        if "Connection refused" in err_msg:
            db_error = "Connection refused (Target DB is offline)"
        else:
            db_error = err_msg.split("\n")[0]

    # 2. Docker Check
    try:
        client = get_docker_client()
        client.ping()
        docker_ok = True
    except Exception as e:
        err_msg = str(e)
        if "Connection refused" in err_msg or "FileNotFoundError" in err_msg:
            docker_error = "Docker daemon is not running"
        else:
            docker_error = err_msg.split("\n")[0]

    # 3. Brain Provider Info
    brain_info = {
        "provider": config.brain.provider,
        "gemini_model": config.brain.gemini.model,
        "gemini_configured": bool(
            config.brain.gemini.api_key
            and config.brain.gemini.api_key != "your_gemini_api_key_here"
        ),
    }

    is_healthy = db_ok and docker_ok

    return {
        "status": "healthy" if is_healthy else "degraded",
        "database": {
            "connected": db_ok,
            "dsn": safe_dsn,
            "error": db_error,
        },
        "docker": {
            "available": docker_ok,
            "error": docker_error,
        },
        "brain": brain_info,
    }


@router.get("/audit")
async def audit_database(limit: int = 10) -> dict[str, Any]:
    config = load_config()
    try:
        async with PsycopgReadAdapter(config.database.dsn) as db:
            observer = Observer(db)
            queries = await observer.fetch_top_queries(limit=limit)

            results = []
            for query_obj, stats in queries:
                try:
                    explain_sql = f"EXPLAIN (FORMAT JSON, COSTS TRUE, GENERIC_PLAN TRUE) {query_obj.raw_query}"
                    res = await db.fetch_one(explain_sql)
                    top_node = "Unknown"
                    cost = 0.0
                    if res:
                        plan_data = res[0] if isinstance(res, list) else res[0]
                        plan = ExplainPlan(plan=plan_data[0]["Plan"])
                        analyzer = Analyzer(plan)
                        scan_nodes = analyzer.find_nodes("Seq Scan")
                        top_node = (
                            scan_nodes[0].node_type
                            if scan_nodes
                            else plan.plan.node_type
                        )
                        cost = analyzer.get_total_cost()

                    results.append(
                        {
                            "query_id": (
                                query_obj.query_id[:16] if query_obj.query_id else "N/A"
                            ),
                            "raw_query": query_obj.raw_query,
                            "calls": stats.calls,
                            "mean_exec_time_ms": round(stats.mean_exec_time, 2),
                            "total_time_ms": round(stats.total_exec_time, 2),
                            "node_type": top_node,
                            "cost": cost,
                        }
                    )
                except Exception:
                    results.append(
                        {
                            "query_id": (
                                query_obj.query_id[:16] if query_obj.query_id else "N/A"
                            ),
                            "raw_query": query_obj.raw_query,
                            "calls": stats.calls,
                            "mean_exec_time_ms": round(stats.mean_exec_time, 2),
                            "total_time_ms": round(stats.total_exec_time, 2),
                            "node_type": "Parameterized",
                            "cost": 0.0,
                        }
                    )

            return {"total": len(results), "queries": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {e}") from e


@router.post("/check")
async def check_query(payload: CheckRequest) -> dict[str, Any]:
    raw_sql = payload.query.strip()
    if not raw_sql:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    cleaned_sql = re.sub(r"/\*.*?\*/", "", raw_sql, flags=re.DOTALL)
    cleaned_sql = re.sub(r"--[^\n]*", "", cleaned_sql).strip()
    lower_sql = cleaned_sql.lower()

    if not any(
        lower_sql.startswith(prefix)
        for prefix in ("select", "with", "insert", "update", "delete")
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Argus-PG analyzes data queries (SELECT, INSERT, UPDATE, DELETE). "
                "DDL and administrative statements (e.g. CREATE, ALTER, DROP, SET) cannot be indexed."
            ),
        )

    config = load_config()

    try:
        async with PsycopgReadAdapter(config.database.dsn) as db:
            explain_sql = (
                f"EXPLAIN (FORMAT JSON, COSTS TRUE, GENERIC_PLAN TRUE) {raw_sql}"
            )
            try:
                res = await db.fetch_one(explain_sql)
            except Exception as e:
                err_msg = str(e).split("\n")[0]
                raise HTTPException(
                    status_code=400,
                    detail=f"PostgreSQL EXPLAIN failed: {err_msg}",
                ) from e

            if not res:
                raise HTTPException(status_code=400, detail="Could not explain query.")

            plan_data = res[0] if isinstance(res, list) else res[0]
            plan = ExplainPlan(plan=plan_data[0]["Plan"])
            schema_extractor = SchemaExtractor(db)

            # Brain selection
            brain: Brain
            if payload.brain_provider == "gemini":
                api_key = payload.gemini_api_key or config.brain.gemini.api_key
                model = payload.gemini_model or config.brain.gemini.model
                brain = GeminiBrain(api_key=api_key, model_name=model)
            else:
                brain = HeuristicBrain()

            query_obj = SqlStatement(raw_query=raw_sql)

            suggestions = await brain.propose_indexes(query_obj, plan)
            if not suggestions:
                return {
                    "status": "no_suggestions",
                    "message": "No indexes suggested. The query may already be optimized or non-indexable.",
                    "suggestions": [],
                }

            # Decision Engine validation with automatic schema extraction
            def sandbox_factory() -> DockerSandbox:
                return DockerSandbox(config.sandbox)

            engine = DecisionEngine(
                sandbox_factory=sandbox_factory, schema_extractor=schema_extractor
            )
            verified = await engine.validate(query_obj, suggestions)

            formatter = ExplanationFormatter()
            reports = []
            for item in verified:
                explanation = formatter.format(
                    before_plan=plan,
                    after_plan=None,
                    index_def=item.definition,
                    result=item.validation,
                )
                reports.append(
                    {
                        "index_name": item.definition.inferred_name,
                        "table_name": item.definition.table_name,
                        "columns": item.definition.columns,
                        "improved": item.validation.improved,
                        "improvement_factor": round(
                            item.validation.improvement_factor, 2
                        ),
                        "original_cost": item.validation.original_cost,
                        "new_cost": item.validation.new_cost,
                        "up_sql": (
                            item.migration.up_sql
                            if item.migration
                            else f"CREATE INDEX {item.definition.inferred_name} ON {item.definition.table_name} ({', '.join(item.definition.columns)});"
                        ),
                        "down_sql": (
                            item.migration.down_sql
                            if item.migration
                            else f"DROP INDEX {item.definition.inferred_name};"
                        ),
                        "reasoning": item.reasoning,
                        "explanation": explanation,
                        "error": item.validation.error,
                    }
                )

            return {
                "status": "success",
                "total_suggestions": len(reports),
                "results": reports,
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/reset-stats")
async def reset_statistics() -> dict[str, Any]:
    """Resets pg_stat_statements statistics on the target database."""
    config = load_config()
    try:
        async with (
            await psycopg.AsyncConnection.connect(
                config.database.dsn, autocommit=True
            ) as aconn,
            aconn.cursor() as cur,
        ):
            await cur.execute("SELECT pg_stat_statements_reset()")
        return {
            "status": "success",
            "message": "pg_stat_statements metrics reset successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to reset statistics: {e}"
        ) from e


@router.post("/apply")
async def apply_migration(payload: ApplyRequest) -> dict[str, Any]:
    """Safely executes a verified CREATE INDEX migration directly on the target database."""
    sql = payload.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="SQL statement cannot be empty")

    upper = sql.upper()
    if not (
        upper.startswith("CREATE INDEX")
        or upper.startswith("CREATE UNIQUE INDEX")
        or upper.startswith("CREATE INDEX CONCURRENTLY")
        or upper.startswith("CREATE UNIQUE INDEX CONCURRENTLY")
    ):
        raise HTTPException(
            status_code=400,
            detail="Only CREATE INDEX statements can be applied via this endpoint",
        )

    config = load_config()
    try:
        async with (
            await psycopg.AsyncConnection.connect(
                config.database.dsn, autocommit=True
            ) as aconn,
            aconn.cursor() as cur,
        ):
            await cur.execute(sql)
        return {
            "status": "success",
            "message": "Index applied successfully to target database",
            "applied_sql": sql,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to apply index: {e}"
        ) from e
