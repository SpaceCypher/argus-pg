import os
import sys
import time

# Ensure src is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import docker
import psycopg

from argus.core.docker_sandbox import get_docker_client

CONTAINER_NAME = "argus-target-demo"
DB_USER = "argus"
DB_PASS = "argus"
DB_NAME = "argus_sandbox"
HOST_PORT = 5444  # Distinct from 5432


def setup_target():
    print(f"Setting up target DB '{CONTAINER_NAME}' on port {HOST_PORT}...")

    # 1. Connect to Docker
    try:
        client = get_docker_client()
    except Exception as e:
        print(f"Failed to connect to Docker: {e}")
        return

    # 2. Cleanup existing
    try:
        old = client.containers.get(CONTAINER_NAME)
        print("Stopping existing container...")
        old.stop()
        old.remove()
    except docker.errors.NotFound:
        pass

    # 3. Start Container
    print("Starting new container...")
    container = client.containers.run(
        "postgres:16-alpine",
        name=CONTAINER_NAME,
        detach=True,
        environment={
            "POSTGRES_USER": DB_USER,
            "POSTGRES_PASSWORD": DB_PASS,
            "POSTGRES_DB": DB_NAME,
        },
        ports={"5432/tcp": HOST_PORT},
        command=[
            "postgres",
            "-c",
            "shared_preload_libraries=pg_stat_statements",
            "-c",
            "pg_stat_statements.track=all",
            "-c",
            "pg_stat_statements.max=10000",
        ],
    )

    # 4. Wait for Ready
    dsn = f"postgresql://{DB_USER}:{DB_PASS}@localhost:{HOST_PORT}/{DB_NAME}"
    print(f"Waiting for Postgres at {dsn}...")

    deadline = time.time() + 30
    conn = None
    while time.time() < deadline:
        try:
            conn = psycopg.connect(dsn, autocommit=True)
            break
        except psycopg.OperationalError:
            time.sleep(1)

    if not conn:
        print("Timeout waiting for DB.")
        container.stop()
        return

    # 5. Seed Data
    print("Seeding data (50k rows)...")
    with conn.cursor() as cur:
        # Enable extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")

        # Create Table
        cur.execute(
            "CREATE TABLE IF NOT EXISTS users (id serial PRIMARY KEY, email text, created_at timestamp DEFAULT now())"
        )

        # Insert 50k rows
        # Using generate_series for speed
        cur.execute("""
            INSERT INTO users (email, created_at)
            SELECT 
                'user_' || i || '@example.com', 
                now() - (i * interval '1 minute')
            FROM generate_series(1, 50000) AS i
        """)

        # Create unindexed slow query scenario
        # We will query by email using LIKE or = without index

        # 6. Generate Load (Slow Query)
        print("Generating load (running slow query 5 times)...")
        slow_query = "SELECT * FROM users WHERE email = 'user_42000@example.com'"
        for _ in range(5):
            cur.execute(slow_query)

    conn.close()
    print("Setup Complete! DSN:", dsn)
    print("Run: poetry run argus audit --dsn", dsn)


if __name__ == "__main__":
    setup_target()
