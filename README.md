# Argus-PG

**Argus-PG** is a sandbox-first PostgreSQL index validation system designed to prevent performance regressions. It provides a deterministic environment to test, verify, and measure the impact of database indexes before they reach production.

## 🚀 Mission

Database performance should not be a guessing game. Argus-PG treats index creation as a rigorously tested code deployment:
1.  **Sandbox**: Spin up ephemeral Dockerized Postgres instances.
2.  **Verify**: Measure query cost and execution time with vs. without the index.
3.  **Decide**: Accept or reject indexes based on concrete regression metrics.

## 🛡 Safety & Security

Argus-PG is designed with a "Safety First" philosophy. It is an **Automated DBA**, not a chaotic monkey.

### ✅ What Argus-PG DOES
-   **Read-Only Observation**: The `Observer` component only runs `EXPLAIN` and reads from `pg_stat_statements`. It NEVER modifies production data.
-   **Sandboxed Experiments**: All `CREATE INDEX` operations happen in an isolated, ephemeral Docker container that is destroyed immediately after validation.
-   **Deterministic Decisions**: Indexes are only recommended if they meet strict quantitative thresholds (e.g., >2x speedup).

### ❌ What Argus-PG Does NOT Do
-   **No Auto-Tuning magic**: It does not wildly change configurations or restart your database.
-   **No AI Hallucinations**: LLM suggestions are treated as *untrusted hypotheses*. If the sandbox validation fails, the suggestion is discarded, no matter how confident the AI was.
-   **No Production Write Access**: Ideally, the configured database user should not even have `CREATE` privileges on production tables.

## 🏗 Architecture

Argus-PG follows a **Hexagonal Architecture** (Ports & Adapters) to ensure separation regarding infrastructure (Docker, Postgres) and core logic.

-   **Domain Layer** (`src/argus/domain`): Pure Python Pydantic models (Queries, Plans, Indexes, Errors). No external dependencies.
-   **Core Layer** (`src/argus/core`): Business logic and abstract interfaces (Sandbox, Observer, Analyzer, Brain).
-   **Interfaces Layer** (`src/argus/interfaces`): CLI and external entry points.

## 🛠 Prerequisites

-   **Python**: 3.11+
-   **Docker**: Running daemon (required for sandbox).
-   **Poetry**: Dependency management.

## 📦 Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/SpaceCypher/argus-pg.git
    cd argus-pg
    ```

2.  **Install dependencies**:
    ```bash
    poetry install
    ```

3.  **Activate virtual environment**:
    ```bash
    poetry shell
    ```

## 🧑‍💻 Development & Testing

### Code Quality
Argus-PG enforces strict coding standards using `ruff`, `black`, and `mypy` (strict mode).

```bash
# Format code
poetry run black .

# Lint code
poetry run ruff check . --fix

# Type check
poetry run mypy .
```

### Running Tests
The test suite covers unit logic, integration (Docker/DB), and failure modes.

```bash
# Run all tests
poetry run pytest

# Run integration tests only (requires Docker)
poetry run pytest -m integration

# Run failure mode verification
poetry run pytest tests/unit/core/test_failure_modes.py
```

## 📊 End-to-End Validation (Case Study)

We successfully validated Argus-PG against a simulated production workload using Google's Gemini 3 model.

### Scenario
-   **Workload**: A PostgreSQL database seeded with 50,000 users.
-   **Problem**: A slow query filtering by email (`SELECT * FROM users WHERE email = '...'`) causing a Seq Scan.
-   **Goal**: Autonomously detect, hypothesize, and validate a fix without human intervention.

### Execution
Command run:
```bash
ARGUS_BRAIN_PROVIDER=gemini \
ARGUS_BRAIN_GEMINI_MODEL=gemini-3-flash-preview \
poetry run python -m argus.cli check query.sql
```

### Results
Argus-PG achieved an **82.34x performance improvement**:
1.  **Detected** high cost Seq Scan.
2.  **Proposed** `idx_users_email` (B-Tree) using Gemini 3 Flash.
3.  **Spun up** an ephemeral Docker sandbox with production-like data.
4.  **Validated** that execution time dropped from **4.46ms** (baseline) to **0.05ms** (indexed).
5.  **Verified** correctness (same results returned).

```
✅ PASS | Improvement: 82.34x (Cost: 4.46 -> 0.05)
Index: idx_users_email
```

## 📝 Usage

### 1. Audit (Read-Only)
Analyze your database for slow queries without making changes.
```bash
poetry run argus audit --dsn "postgresql://user:pass@host:5432/db"
```

### 2. Check (Validation)
Test a specific query file to see if Argus can optimize it.
```bash
poetry run argus check query.sql
```

### 3. Watch (Autonomous Mode)
Run as a daemon to continuously optimize the database.
```bash
poetry run argus watch
```

## 🗺 Roadmap

-   **Phase 1**: Domain Models (Completed)
-   **Phase 2**: Sandbox Engine (Completed)
-   **Phase 3**: Observation & Analysis (Completed)
-   **Phase 4**: Decision Engine & LLM Integration (Completed - Gemini 3 supported)
-   **Phase 5**: CLI & Production interface (Completed)
-   **Phase 6**: Verification & Testing (Completed)

## 📄 License

[MIT](LICENSE) (Pending)
