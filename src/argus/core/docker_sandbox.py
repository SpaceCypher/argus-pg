import os
from typing import Any, Self

import docker
from docker.errors import APIError, DockerException
from docker.models.containers import Container

from argus.core.sandbox import Sandbox
from argus.domain.errors import DependencyError
from argus.domain.index import IndexDefinition
from argus.domain.query import PgStatStats, SqlStatement
from argus.domain.sandbox import SandboxConfig


def get_docker_client() -> docker.DockerClient:
    """
    Instantiate Docker client with automatic detection of macOS Colima,
    Docker Desktop, OrbStack, or standard environment sockets.
    """
    # 1. Try standard environment
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception:
        pass

    # 2. Probe candidate unix sockets on macOS / Linux
    home = os.path.expanduser("~")
    candidates = [
        os.environ.get("DOCKER_HOST"),
        f"unix://{home}/.colima/default/docker.sock",
        f"unix://{home}/.docker/run/docker.sock",
        f"unix://{home}/.orbstack/run/docker.sock",
        "unix:///var/run/docker.sock",
    ]

    for candidate in candidates:
        if not candidate:
            continue
        sock_path = candidate.replace("unix://", "")
        if os.path.exists(sock_path):
            try:
                base_url = (
                    candidate
                    if candidate.startswith("unix://")
                    else f"unix://{candidate}"
                )
                client = docker.DockerClient(base_url=base_url)
                client.ping()
                return client
            except Exception:
                continue

    # Fallback to from_env to raise canonical DockerException
    return docker.from_env()


class DockerSandbox(Sandbox):
    """
    Concrete implementation of Sandbox using the Python Docker SDK.
    Manages an ephemeral Postgres container.
    """

    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        try:
            self._client: docker.DockerClient = get_docker_client()
        except Exception as e:
            raise DependencyError(f"Docker infrastructure failed: {e}") from e
        self._container: Container | None = None

    async def __aenter__(self) -> Self:
        """
        Provision the Docker container.
        1. Pull image
        2. Run container
        3. Wait for readiness (simple sleep/check for now, real check later)
        """
        try:
            # PULL
            try:
                self._client.images.get(self.config.image)
            except docker.errors.ImageNotFound:
                print(f"Pulling image {self.config.image}...")
                self._client.images.pull(self.config.image)

            # RUN
            # We map 5432 to a random port
            self._container = self._client.containers.run(
                self.config.image,
                detach=True,
                remove=True,  # Auto-remove on stop
                environment={
                    "POSTGRES_PASSWORD": "argus",
                    "POSTGRES_USER": "argus",
                    "POSTGRES_DB": "argus_sandbox",
                },
                ports={"5432/tcp": None},  # Bind to random host port
                shm_size="256mb",
                command=[
                    "postgres",
                    "-c",
                    "shared_preload_libraries=pg_stat_statements",
                    "-c",
                    "pg_stat_statements.track=all",
                ],
            )

            # REFRESH to get mapped ports
            if self._container:  # type guard
                self._container.reload()

            # WAIT Logic
            try:
                await self._wait_for_ready()
            except TimeoutError as e:
                # Cleanup if we fail to start
                if self._container:
                    self._container.stop()
                raise DependencyError(f"Postgres failed to become ready: {e}") from e

            return self

        except (DockerException, APIError) as e:
            raise DependencyError(f"Docker infrastructure failed: {str(e)}") from e

    async def _wait_for_ready(self) -> None:
        """
        Polls the Postgres container until it accepts connections or timeouts.
        """
        import asyncio
        import time

        import psycopg

        if not self._container:
            raise DependencyError("Container not initialized")

        # Get host port
        ports = self._container.ports
        if not ports or "5432/tcp" not in ports or not ports["5432/tcp"]:
            raise DependencyError("Container port 5432 is not exposed")

        host_port = ports["5432/tcp"][0]["HostPort"]
        dsn = f"postgresql://argus:argus@localhost:{host_port}/argus_sandbox"

        deadline = time.time() + self.config.timeout_seconds

        while time.time() < deadline:
            try:
                # Try to connect
                with (
                    psycopg.connect(dsn, autocommit=True) as conn,
                    conn.cursor() as cur,
                ):
                    cur.execute("SELECT 1")
                    # Ensure extension is created
                    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
                return  # Success
            except psycopg.OperationalError:
                # DB not ready yet
                await asyncio.sleep(0.5)
            except Exception as e:
                # Unknown error, maybe fatal, but retry to be safe
                print(f"Readiness check warning: {e}")
                await asyncio.sleep(0.5)

        raise TimeoutError(
            f"Timed out after {self.config.timeout_seconds}s waiting for Postgres"
        )

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Cleanup: Stop the container.
        """
        if self._container:
            try:
                self._container.stop()
                # self._container.remove() # handled by remove=True in run
                self._container = None
            except Exception as e:
                # Log but don't crash teardown
                print(f"Warning: Failed to stop sandbox container: {e}")

    async def _execute_sql(self, sql: str, fetch: bool = False) -> Any:
        if not self._container:
            raise DependencyError("Container not initialized")

        host_port = self._container.ports["5432/tcp"][0]["HostPort"]
        dsn = f"postgresql://argus:argus@localhost:{host_port}/argus_sandbox"

        # Keeping local to avoid module-level strict dependency
        import psycopg

        try:
            with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
                cur.execute(sql)
                if fetch:
                    return cur.fetchall()
                return None
        except Exception as e:
            raise DependencyError(f"SQL Execution failed: {e}") from e

    async def reset_metrics(self) -> None:
        await self._execute_sql("SELECT pg_stat_statements_reset()")

    async def seed(self, sql: str) -> None:
        """
        Execute raw SQL against the running container to seed schema/data.
        """
        await self._execute_sql(sql)

    async def run_query(self, query: SqlStatement) -> PgStatStats:
        # 1. Execute the query
        await self._execute_sql(query.raw_query)

        # 2. Fetch stats
        # We assume the query text matches closely enough for now.
        # Since we just ran it, and we reset execution, ideally it's the top one.
        # But for robustness, we try to match query text.
        # Postgres normalizes query text (strips comments, specific spacing).
        # For this phase, returning the most resource-intensive recent query is decent.
        # Actually, let's just grab the row with the highest execution count.

        # NOTE: pg_stat_statements might replace literals with parems ($1).
        # We enabled track=all.

        stats_sql = """
            SELECT calls, total_exec_time, rows
            FROM pg_stat_statements
            ORDER BY total_exec_time DESC
            LIMIT 1
        """
        # In a generic sandbox, grabbing the top query is risky.
        # But this is a controlled sandbox.

        rows = await self._execute_sql(stats_sql, fetch=True)
        if not rows:
            # Maybe the query was too fast or track failed?
            return PgStatStats(calls=0, total_exec_time=0.0, rows=0)

        call_count, total_time, row_count = rows[0]
        return PgStatStats(calls=call_count, total_exec_time=total_time, rows=row_count)

    async def apply_index(self, index: IndexDefinition) -> None:
        # Generate DDL
        col_str = ", ".join(index.columns)
        unique_str = "UNIQUE " if index.unique else ""
        # We'll skip CONCURRENTLY for simplicity unless strictly needed.
        ddl = (
            f"CREATE {unique_str}INDEX {index.inferred_name} "
            f"ON {index.schema_name}.{index.table_name} "
            f"USING {index.method} ({col_str})"
        )

        await self._execute_sql(ddl)
