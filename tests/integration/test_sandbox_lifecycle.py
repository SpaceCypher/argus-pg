import pytest

from argus.core.docker_sandbox import DockerSandbox
from argus.domain.sandbox import SandboxConfig


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sandbox_boot_and_teardown():
    """Verify that the sandbox starts a container and tears it down."""
    try:
        config = SandboxConfig(postgres_image="postgres:16-alpine")
        sandbox = DockerSandbox(config)

        async with sandbox as sb:
            # Container should be running
            # We can verify by interacting with it using low level client or just running a query
            # Since we don't expose the docker client directly in public interface (only via private _client)
            # We'll rely on seed/run_query to prove it's up.

            # Simple health check
            res = await sb._execute_sql("SELECT 1", fetch=True)
            assert len(res) == 1
            assert res[0][0] == 1

    except Exception as e:
        pytest.fail(f"Sandbox lifecycle failed: {e}")
    # After exit, container should be gone.
    # DockerSandbox currently doesn't expose a way to check if container exists after cleanup from the wrapper.
    # We assume cleanup works if no exceptions.


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sandbox_seeding():
    """Verify seeding applies schema and data."""
    try:
        config = SandboxConfig(postgres_image="postgres:16-alpine")
        sandbox = DockerSandbox(config)

        async with sandbox as sb:
            ddl = "CREATE TABLE integration_test (id int);"
            await sb.seed(ddl)

            data = "INSERT INTO integration_test (id) VALUES (42);"
            await sb.seed(data)

            # Verify data
            res = await sb._execute_sql("SELECT id FROM integration_test", fetch=True)
            assert len(res) == 1
            assert res[0][0] == 42

    except Exception as e:
        pytest.fail(f"Sandbox seeding failed: {e}")
