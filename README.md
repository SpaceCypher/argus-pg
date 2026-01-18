# Argus-PG

**Argus-PG** is a sandbox-first PostgreSQL index validation system designed to prevent performance regressions. It provides a deterministic environment to test, verify, and measure the impact of database indexes before they reach production.

## 🚀 Mission

Database performance should not be a guessing game. Argus-PG treats index creation as a rigorously tested code deployment:
1.  **Sandbox**: Spin up ephemeral Dockerized Postgres instances.
2.  **Verify**: Measure query cost and execution time with vs. without the index.
3.  **Decide**: Accept or reject indexes based on concrete regression metrics.

## 🏗 Architecture

Argus-PG follows a **Hexagonal Architecture** (Ports & Adapters) to ensure separation regarding infrastructure (Docker, Postgres) and core logic.

-   **Domain Layer** (`src/argus/domain`): Pure Python Pydantic models (Queries, Plans, Indexes, Errors). No external dependencies.
-   **Core Layer** (`src/argus/core`): Business logic and abstract interfaces (Sandbox, Observer, Analyzer).
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

## 🧑‍💻 Development

### Workflow
We enforce strict Git and coding discipline:
-   **Atomic Tasks**: One task = One branch.
-   **Linear History**: Squash merge to `main`.
-   **Strict Typing**: 100% MyPy strict mode coverage.

### Code Quality
Run the full suite of linters and formatters:

```bash
# Format code
poetry run black .

# Lint code (with autofix)
poetry run ruff check . --fix

# Type check
poetry run mypy .
```

### Project Structure
```
argus-pg/
├── src/argus/
│   ├── domain/       # Pydantic models & Vocabulary
│   ├── core/         # Business Logic & Interfaces
│   └── interfaces/   # CLI & Adapters
├── tests/            # Test suite
├── poetry.lock
├── pyproject.toml    # Dependencies & Tool Config
├── WORK_PLAN.md      # High-level Roadmap
└── WORK_STATUS.md    # Active Task Tracking
```

## 🗺 Roadmap

-   **Phase 1**: Domain Models (Completed)
    -   Query, Plan, Index, Sandbox, Errors.
-   **Phase 2**: Sandbox Engine (In Progress)
    -   Abstract Interface, Docker Adapter, Lifecycle management.
-   **Phase 3**: Observation & Analysis
-   **Phase 4**: Decision Engine (Heuristic/LLM)
-   **Phase 5**: CLI & Production interface

## 📄 License

[MIT](LICENSE) (Pending)
