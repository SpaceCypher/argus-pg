# Argus-PG

**Argus-PG** is a sandbox-first PostgreSQL index validation system designed to eliminate "Database Drift" and prevent performance regressions. It provides an autonomous, deterministic environment to test, verify, and mathematically measure the impact of database indexes before they reach production.

🌐 **Landing Page**: [https://argus-tau.vercel.app/](https://argus-tau.vercel.app/)

## 🚀 Mission

Database performance should not be a guessing game. Argus-PG treats index creation as a rigorously tested code deployment:
1. **Introspect & Hydrate ("Synthetic Twin")**: Automatically extracts table schemas, constraints, and column types from your target database, and hydrates the sandbox with type-accurate synthetic data using realistic selectivity.
2. **Sandbox**: Spin up ephemeral Dockerized Postgres instances.
3. **Verify**: Measure baseline execution time/cost, apply the candidate index, and re-benchmark in isolation.
4. **Decide & Act**: Accept or reject indexes based on quantitative speedup thresholds (e.g., >2x speedup) and output production-ready migration DDL (`CREATE INDEX CONCURRENTLY`).

## 🛡 Safety & Security

Argus-PG is designed with a "Safety First" philosophy. It is an **Automated DBA**, not a chaotic monkey.

### ✅ What Argus-PG DOES
- **Read-Only Observation**: The `Observer` component only runs `EXPLAIN` and reads from `pg_stat_statements` with session-level `TRANSACTION READ ONLY`. It NEVER modifies production data.
- **Sandboxed Experiments**: All `CREATE INDEX` operations happen in an isolated, ephemeral Docker container that is destroyed immediately after validation.
- **Synthetic Twin**: Generates synthetic data matching target column types and query predicates so no production customer data is ever copied into the sandbox.
- **Deterministic Decisions**: Indexes are only recommended if they meet strict quantitative thresholds (e.g., >2x speedup).

### ❌ What Argus-PG Does NOT Do
- **No Auto-Tuning magic**: It does not wildly change configurations or restart your database.
- **No AI Hallucinations**: LLM suggestions are treated as *untrusted hypotheses*. If the sandbox validation fails, the suggestion is discarded, no matter how confident the AI was.
- **No Production Write Access**: The configured database user requires only `SELECT` privileges on system catalogs and tables.

## 📝 Commands

### 1. `argus audit` — Read-Only Telemetry Analysis
Analyze your database for slow queries without making changes.

```bash
ARGUS_DATABASE_DSN=postgresql://user:pass@host:5432/db \
poetry run python -m argus.cli audit --limit 5 --filter-small-tables
```

**Example Output:**
```
🔍 Analyzing top 5 slow queries...
Target DB: postgresql://argus:argus@localhost:5444/argus_sandbox

Fingerprint      | Calls    | Mean(ms)   | Node Type       | Cost      
---------------------------------------------------------------------------
f3f58600e971f1be | 3        | 5.22       | Seq Scan        | 1042.00   
```

---

### 2. `argus check` — Validate & Fix (with Automated Hydration)
Test a specific query file. Argus clones the table schema, hydrates synthetic data in a temporary Docker container, and verifies the speedup.

```bash
ARGUS_DATABASE_DSN=postgresql://user:pass@host:5432/db \
ARGUS_BRAIN_PROVIDER=heuristic \
poetry run python -m argus.cli check query.sql --explain
```

**Example Output (145x Speedup!):**
```
🔍 Checking query from query.sql...
Brain: heuristic
🧠 Brain proposed 1 indexes. Validating in Sandbox...

=== Validation Report ===

✅ PASS | Improvement: 145.71x (Cost: 7.17 -> 0.05)
Index: idx_users_email
DDL:
CREATE INDEX CONCURRENTLY idx_users_email ON "public"."users" USING btree ("email");

--- Explanation ---
Bottleneck:
- Planner used Seq Scan on users
- Filtered on (email = 'user_42000@example.com'::text)
- Estimated 1 rows scanned

Resolution:
- Index idx_users_email applied
- Speedup: 145.71x
- Cost: 7.17 -> 0.05
```

---

### 3. `argus watch` — Autonomous Mode
Run as a daemon to continuously monitor queries and validate optimizations in the background.

```bash
ARGUS_DATABASE_DSN=postgresql://user:pass@host:5432/db \
poetry run python -m argus.cli watch --interval 60
```

---

### 4. `argus dashboard` — Web Mission Control UI
Launch the interactive web dashboard and REST API on port 8000:

```bash
poetry run python -m argus.cli dashboard --host 127.0.0.1 --port 8000
# Open http://localhost:8000 in your browser
```

---

### Using Gemini AI Brain
Replace heuristics with Google Gemini for advanced indexing hypotheses (PII redacted):

```bash
ARGUS_BRAIN_PROVIDER=gemini \
ARGUS_BRAIN_GEMINI_API_KEY=your_api_key \
ARGUS_BRAIN_GEMINI_MODEL=gemini-3.5-flash \
poetry run python -m argus.cli check query.sql --explain
```

## 🏗 Architecture

Argus-PG follows a **Hexagonal Architecture** (Ports & Adapters):

- **Domain Layer** (`src/argus/domain`): Pure Python Pydantic models (Queries, Plans, Indexes, Errors).
- **Core Layer** (`src/argus/core`): Business logic:
  - `DockerSandbox`: Ephemeral container lifecycle and benchmark execution.
  - `SchemaExtractor`: PostgreSQL catalog introspection & DDL extraction.
  - `DataHydrator`: Synthetic Twin data generator with cardinality simulation.
  - `Observer`: Read-only telemetry collector with `pg_class` size heuristics.
  - `Analyzer` & `Fingerprinter`: Plan AST traversal and `sqlglot` SQL canonicalization.
  - `HeuristicBrain` & `GeminiBrain`: Rule-based & LLM index hypothesis generators.
  - `DecisionEngine`: Validation orchestrator & migration generator.
- **Interfaces Layer** (`src/argus/interfaces`): CLI (`argus.cli`), Explanation Formatter, and FastAPI Web Dashboard (`argus.interfaces.web`).

## 🛠 Prerequisites

- **Python**: 3.11+
- **Docker**: Running daemon (for ephemeral sandbox execution).
- **Poetry**: Dependency management.

## 📦 Installation & Quickstart

```bash
git clone https://github.com/SpaceCypher/argus-pg.git
cd argus-pg
poetry install
poetry shell
```

## 🧑‍💻 Developer Commands (Makefile)

```bash
make test         # Run unit tests
make lint         # Lint with ruff & black
make format       # Format code
make typecheck    # Run mypy strict type checker
make dashboard    # Launch Web Mission Control
make demo         # Setup demo PostgreSQL target with 50k rows
```

## 🗺 Roadmap

| Phase | Status |
|---|---|
| Domain Models | ✅ Complete |
| Sandbox Engine & Docker Lifecycle | ✅ Complete |
| Automated Schema Extraction & Catalog Introspection | ✅ Complete |
| Synthetic Twin Hydration & Cardinality Simulation | ✅ Complete |
| Observation & Analysis (`pg_class` heuristics + `sqlglot` AST) | ✅ Complete |
| Decision Engine & Gemini AI Integration | ✅ Complete |
| CLI & Migration DDL Generator | ✅ Complete |
| Web Mission Control Dashboard & REST API | ✅ Complete |
| Production Dockerfile & Developer Tooling | ✅ Complete |
| Unit & Failure Mode Verification Suite | ✅ Complete |
| PR Comment Bot (PyGithub integration) | 🚧 In Progress |

## 📄 License

[MIT](LICENSE)
