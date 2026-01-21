from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from docker.errors import DockerException

from argus.config import DatabaseConfig
from argus.core.database import PsycopgReadAdapter
from argus.core.docker_sandbox import DockerSandbox
from argus.core.gemini_brain import GeminiBrain
from argus.domain.errors import DependencyError
from argus.domain.plans import ExplainPlan, PlanNode
from argus.domain.query import SqlStatement
from argus.domain.sandbox import SandboxConfig


# --- 1. Docker Unavailable ---
def test_sandbox_docker_unavailable():
    """Verify DependencyError when Docker client cannot be initialized."""
    with patch("docker.from_env", side_effect=DockerException("Connection refused")):
        config = SandboxConfig(postgres_image="postgres:16-alpine")

        # Should raise immediately on init if we check there, or on usage.
        # DockerSandbox initializes client in __init__.
        with pytest.raises(DependencyError) as exc:
            DockerSandbox(config)
        assert "Docker infrastructure failed" in str(exc.value)


# --- 2. Sandbox Startup Failure ---
@pytest.mark.asyncio
async def test_sandbox_startup_timeout():
    """Verify cleanup happens if sandbox fails to become ready."""
    # Mock client and container
    mock_client = MagicMock()
    mock_container = MagicMock()
    # Mock ports to look valid initially so we get past the first check,
    # but fail the readiness loop?
    # Actually, let's make readiness check time out.
    mock_container.ports = {"5432/tcp": [{"HostPort": "12345"}]}
    mock_client.containers.run.return_value = mock_container

    config = SandboxConfig(postgres_image="pg", container_timeout_sec=1)

    with patch("docker.from_env", return_value=mock_client):
        sandbox = DockerSandbox(config)

        # Mock _wait_for_ready to raise TimeoutError
        # (We could also mock time.time and sleep to really simulate it, but mocking the method is cleaner for unit test)
        with patch.object(
            sandbox, "_wait_for_ready", side_effect=TimeoutError("Timed out")
        ):
            with pytest.raises(DependencyError) as exc:
                async with sandbox:
                    pass

            assert "Postgres failed to become ready" in str(exc.value)

            # CRITICAL: Verify cleanup (stop) was called
            mock_container.stop.assert_called_once()


# --- 3. LLM Unavailable ---
@pytest.mark.asyncio
async def test_brain_llm_failure():
    """Verify GeminiBrain returns empty list on API failure (graceful fallback)."""
    brain = GeminiBrain(api_key="fake", model_name="gemini-fake")

    query = SqlStatement(
        query_id="q1", raw_query="SELECT 1", calls=1, total_exec_time=1.0, rows=1
    )
    plan = ExplainPlan(
        plan=PlanNode(
            node_type="Seq Scan",
            total_cost=10.0,
            startup_cost=0.0,
            plan_rows=100,
            plan_width=4,
            plans=[],
        )
    )

    # Mock the generative model to raise exception
    with patch("google.generativeai.GenerativeModel") as MockModel:
        mock_chat = AsyncMock()
        mock_chat.send_message_async.side_effect = Exception("API Quota Exceeded")

        instance = MockModel.return_value
        instance.start_chat.return_value = mock_chat

        # Should NOT raise, but return empty list
        suggestions = await brain.propose_indexes(query, plan)
        assert suggestions == []
        # Optionally check if we logged an error, but return value is key contract.


# --- 4. No Improvement (Degradation) ---
# Check tests/unit/core/test_decision_engine.py -> test_decision_engine_validate_degradation
# That test already covers this scenario. We won't duplicate it here unless we need specific failure variants.
# We will trust the existing unit test for this failure mode.


# --- 5. Invalid SQL ---
@pytest.mark.asyncio
async def test_sandbox_invalid_sql():
    """Verify invalid SQL raises DependencyError (wrapping the DB error)."""
    config = SandboxConfig(postgres_image="pg")

    # We need a functional sandbox logic without real docker
    # So we mock the _execute_sql method? Or mock psycopg inside it?
    # Using partial mock of the class might be best.

    with patch("docker.from_env"):
        sandbox = DockerSandbox(config)
        # We cheat and say it's initialized
        sandbox._container = MagicMock()
        sandbox._container.ports = {"5432/tcp": [{"HostPort": "5432"}]}

        import psycopg

        with patch(
            "psycopg.connect", side_effect=psycopg.OperationalError("Syntax Error")
        ):
            with pytest.raises(DependencyError) as exc:
                await sandbox._execute_sql("SELECT * FROM non_existent")

            assert "SQL Execution failed" in str(exc.value)


# --- 6. Target DB Connection Failure ---
# Assuming we had a unit test for PsycopgReadAdapter.
# Let's add one here if missing, or check Adapter tests.
# We haven't built tests/unit/core/test_database.py yet?
# Let's add a quick verification here.


@pytest.mark.asyncio
async def test_read_adapter_connection_failure():
    """Verify database connection failure is caught."""
    config = DatabaseConfig(dsn="postgresql://bad:host/db")
    adapter = PsycopgReadAdapter(config)

    import psycopg

    with patch(
        "psycopg.AsyncConnection.connect",
        side_effect=psycopg.OperationalError("Connection failed"),
    ):
        with pytest.raises(DependencyError) as exc:
            async with adapter:
                pass

        assert "Database connection failed" in str(exc.value)
