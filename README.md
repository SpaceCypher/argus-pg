# Argus-PG

**Argus-PG** is a sandbox-first PostgreSQL index validation system designed to prevent performance regressions. It provides a deterministic environment to test, verify, and measure the impact of database indexes before they reach production.

🌐 **Landing Page**: [https://argus-tau.vercel.app/](https://argus-tau.vercel.app/)

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

## 📝 Commands

### 1. `argus audit` — Read-Only Analysis
Analyze your database for slow queries without making changes.

```bash
ARGUS_DATABASE_DSN=postgresql://user:pass@host:5432/db \
poetry run python -m argus.cli audit --limit 5
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

### 2. `argus check` — Validate & Fix
Test a specific query file to see if Argus can optimize it with an index.

```bash
ARGUS_DATABASE_DSN=postgresql://user:pass@host:5432/db \
ARGUS_SANDBOX_IMAGE=postgres:16-alpine \
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
DDL: (Available in IndexDefinition, migration plan not generated)

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
Run as a daemon to continuously monitor and optimize.

```bash
ARGUS_DATABASE_DSN=postgresql://user:pass@host:5432/db \
poetry run python -m argus.cli watch --interval 60
```

---

### Using Gemini AI Brain
Replace heuristics with Google Gemini for smarter suggestions:

```bash
ARGUS_BRAIN_PROVIDER=gemini \
ARGUS_BRAIN_GEMINI_API_KEY=your_api_key \
ARGUS_BRAIN_GEMINI_MODEL=gemini-3-flash-preview \
poetry run python -m argus.cli check query.sql --explain
```

## 🏗 Architecture

Argus-PG follows a **Hexagonal Architecture** (Ports & Adapters):

-   **Domain Layer** (`src/argus/domain`): Pure Python Pydantic models (Queries, Plans, Indexes, Errors).
-   **Core Layer** (`src/argus/core`): Business logic (Sandbox, Observer, Analyzer, Brain).
-   **Interfaces Layer** (`src/argus/interfaces`): CLI and external entry points.

## 🛠 Prerequisites

-   **Python**: 3.11+
-   **Docker**: Running daemon (for sandbox).
-   **Poetry**: Dependency management.

## 📦 Installation

```bash
git clone https://github.com/SpaceCypher/argus-pg.git
cd argus-pg
poetry install
poetry shell
```

## 🧑‍💻 Development & Testing

### Code Quality
```bash
poetry run black .          # Format
poetry run ruff check . --fix  # Lint
poetry run mypy .           # Type check
```

### Running Tests
```bash
poetry run pytest                                    # All tests
poetry run pytest -m integration                     # Integration only
poetry run pytest tests/unit/core/test_failure_modes.py  # Failure modes
```

## 📊 Validated Performance Metrics

| Test Case | Brain | Before (ms) | After (ms) | Speedup |
|-----------|-------|-------------|------------|---------|
| Email filter on 50k users | Heuristic | 7.17 | 0.05 | **145.71x** |
| Email filter on 50k users | Gemini 3 | 4.46 | 0.05 | **82.34x** |

## 🗺 Roadmap

| Phase | Status |
|-------|--------|
| Domain Models | ✅ Complete |
| Sandbox Engine | ✅ Complete |
| Observation & Analysis | ✅ Complete |
| Decision Engine & LLM | ✅ Complete (Gemini 3) |
| CLI & Production Interface | ✅ Complete |
| Verification & Testing | ✅ Complete |
| Release Hardening (v0.1.0) | ✅ Complete |
| Explanation Layer | ✅ Complete |
| Landing Page | ✅ Complete |
| PR Comment Bot | 🚧 In Progress |

## 📄 License

[MIT](LICENSE)
