from typing import Any, Self

import docker
from docker.errors import APIError, DockerException
from docker.models.containers import Container

from argus.core.sandbox import Sandbox
from argus.domain.errors import DependencyError
from argus.domain.index import IndexDefinition
from argus.domain.query import PgStatStats, SqlStatement
from argus.domain.sandbox import SandboxConfig


class DockerSandbox(Sandbox):
    """
    Concrete implementation of Sandbox using the Python Docker SDK.
    Manages an ephemeral Postgres container.
    """

    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        self._client: docker.DockerClient = docker.from_env()
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
                self._client.images.get(self.config.postgres_image)
            except docker.errors.ImageNotFound:
                print(f"Pulling image {self.config.postgres_image}...")
                self._client.images.pull(self.config.postgres_image)

            # RUN
            # We map 5432 to a random port
            self._container = self._client.containers.run(
                self.config.postgres_image,
                detach=True,
                remove=True,  # Auto-remove on stop
                environment={
                    "POSTGRES_PASSWORD": "argus",
                    "POSTGRES_USER": "argus",
                    "POSTGRES_DB": "argus_sandbox",
                },
                ports={"5432/tcp": None},  # Bind to random host port
                shm_size=self.config.shared_buffers,  # Respect config
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

        deadline = time.time() + self.config.container_timeout_sec

        while time.time() < deadline:
            try:
                # Try to connect
                with (
                    psycopg.connect(dsn, autocommit=True) as conn,
                    conn.cursor() as cur,
                ):
                    cur.execute("SELECT 1")
                return  # Success
            except psycopg.OperationalError:
                # DB not ready yet
                await asyncio.sleep(0.5)
            except Exception as e:
                # Unknown error, maybe fatal, but retry to be safe
                print(f"Readiness check warning: {e}")
                await asyncio.sleep(0.5)

        raise TimeoutError(
            f"Timed out after {self.config.container_timeout_sec}s waiting for Postgres"
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

    async def reset_metrics(self) -> None:
        # Task 2.3+
        raise NotImplementedError("Task 2.3")

    async def seed(self, sql: str) -> None:
        """
        Execute raw SQL against the running container to seed schema/data.
        """
        if not self._container:
            raise DependencyError("Container not initialized")

        # We assume _wait_for_ready has passed, so ports are available.
        host_port = self._container.ports["5432/tcp"][0]["HostPort"]
        dsn = f"postgresql://argus:argus@localhost:{host_port}/argus_sandbox"

        # Keeping local to avoid module-level strict dependency
        import psycopg

        try:
            with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
                cur.execute(sql)
        except Exception as e:
            raise DependencyError(f"Seeding failed: {e}") from e

    async def run_query(self, query: SqlStatement) -> PgStatStats:
        # Task 2.5
        raise NotImplementedError("Task 2.5")

    async def apply_index(self, index: IndexDefinition) -> None:
        # Task 2.4/2.5
        raise NotImplementedError("Task 2.5")
