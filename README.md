# Argus-PG

<p align="center">
  <img src="https://raw.githubusercontent.com/SpaceCypher/argus-pg/main/src/argus/interfaces/web/static/favicon.ico" width="80" alt="Argus-PG Logo" onerror="this.style.display='none'"/>
</p>

<h3 align="center">Sandbox-First Autonomous PostgreSQL Index Advisor & Validator</h3>

<p align="center">
  <a href="https://github.com/SpaceCypher/argus-pg/actions"><img src="https://img.shields.io/badge/tests-26%20passed-brightgreen?style=flat-square" alt="Tests"/></a>
  <a href="https://github.com/SpaceCypher/argus-pg"><img src="https://img.shields.io/badge/typecheck-mypy%20strict-blue?style=flat-square" alt="Type Check"/></a>
  <a href="https://github.com/SpaceCypher/argus-pg"><img src="https://img.shields.io/badge/python-3.11%20%7C%203.12-blue?style=flat-square" alt="Python Version"/></a>
  <a href="https://github.com/SpaceCypher/argus-pg"><img src="https://img.shields.io/badge/postgres-14%2B%20%7C%2016-336791?style=flat-square" alt="PostgreSQL"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-purple?style=flat-square" alt="License"/></a>
</p>

<p align="center">
  🌐 <strong>Landing Page & Demo</strong>: <a href="https://argus-tau.vercel.app/">https://argus-tau.vercel.app/</a>
</p>

---

## 🎯 What is Argus-PG?

**Argus-PG** is a sandbox-first database optimization engine. It continuously observes PostgreSQL telemetry (`pg_stat_statements`), detects unindexed sequential scans, and validates index hypotheses inside **isolated, ephemeral Docker containers** before any DDL reaches production.

Unlike conventional query analyzers that merely guess based on static rules or unverified LLM prompts, Argus-PG:
1. **Introspects Table Schemas**: Extracts live catalog DDL, constraints, primary keys, and custom ENUM types.
2. **Hydrates a Synthetic Twin**: Generates statistical datasets in the sandbox matching query predicate selectivity without exposing customer PII.
3. **Benchmarks in an Ephemeral Sandbox**: Provisions clean PostgreSQL containers to measure baseline vs. indexed execution time.
4. **Outputs Reversible Migrations**: Generates non-blocking `CREATE INDEX CONCURRENTLY` DDL and `DROP INDEX CONCURRENTLY IF EXISTS` rollbacks.

```mermaid
flowchart LR
    A[Target PostgreSQL\npg_stat_statements] -->|Extract Query & Catalog| B(Argus-PG Core)
    B -->|Propose Index| C[AI Brain / AST Rules\nGemini 3.5-Flash]
    C -->|Hypothesis| D[Ephemeral Docker Sandbox]
    B -->|Clone DDL & Hydrate| D
    D -->|A/B Latency Benchmark| E{Speedup > Threshold?}
    E -->|Yes| F[✅ Verified Migration\nCREATE INDEX CONCURRENTLY]
    E -->|No| G[❌ Discard Hypothesis]
```

---

## 🛡 Safety & Security Model

Argus-PG is an **Automated DBA**, not an intrusive tuning agent.

* **Read-Only by Default**: The `Observer` reads only from `pg_stat_statements` and system catalogs with session-level `TRANSACTION READ ONLY`.
* **Zero Production Data Leakage**: No production records are ever cloned. The `DataHydrator` generates synthetic data on-the-fly.
* **Deterministic Verification**: AI-generated suggestions are treated as unverified hypotheses. If the isolated sandbox fails to prove a latency reduction, the suggestion is discarded.
* **Non-Blocking DDL**: All migrations use `CREATE INDEX CONCURRENTLY` to avoid table write locks.

---

## ⚡ Quickstart

### 1. Installation

```bash
git clone https://github.com/SpaceCypher/argus-pg.git
cd argus-pg
poetry install
cp .env.example .env
```

### 2. Setup a Demo Target Database

Spin up a seeded PostgreSQL container (50k rows with unindexed slow queries):

```bash
make setup-demo
```

### 3. Launch Mission Control Dashboard

Start the web UI and REST API on `http://127.0.0.1:8000`:

```bash
make dashboard
```

---

## 🖥 Mission Control Web Interface

The web dashboard provides a full glassmorphism control panel:

* **⚡ Optimization Playground**: Interactive SQL editor to test queries against the sandbox with Heuristic or Google Gemini AI brains.
* **🔍 Target Database Telemetry**: Live `pg_stat_statements` viewer with 1-click sandbox testing per slow query.
* **📊 Quantitative Verification Cards**: Visual before/after latency cost comparisons, verified speedup factor, and bottleneck breakdown.
* **🔒 1-Click Migration Actions**:
  * `📋 Copy Up SQL` (`CREATE INDEX CONCURRENTLY`)
  * `↩️ Copy Rollback SQL` (`DROP INDEX CONCURRENTLY IF EXISTS`)
  * `💾 Export Migration (.sql)` (Download Flyway/Prisma compatible migration scripts)
  * `🔒 Apply to Target DB` (Safe interactive execution)

---

## 💻 CLI Commands

### 1. `argus audit` — Telemetry Analysis
Scan your database for slow queries and sequential scans:

```bash
poetry run python -m argus.cli audit --limit 10 --filter-small-tables
```

**Example Output:**
```text
🔍 Analyzing top 10 slow queries...
Target DB: postgresql://argus:argus@localhost:5444/argus_sandbox

Fingerprint      | Calls    | Mean(ms)   | Node Type       | Cost      
---------------------------------------------------------------------------
f3f58600e971f1be | 5        | 2.02       | Seq Scan        | 1042.00   
165a22d8eabe300a | 80       | 0.03       | Result          | 0.01      
```

---

### 2. `argus check` — AI Sandbox Validation
Validate a query file and prove speedup with automated schema cloning and synthetic hydration:

```bash
poetry run python -m argus.cli check query.sql --explain
```

**Example Output:**
```text
🔍 Checking query from query.sql...
Brain: gemini (gemini-3.5-flash)
🧠 Brain proposed 1 indexes. Validating in Sandbox...

=== Validation Report ===

✅ PASS | Improvement: 24.94x (Cost: 1.07 -> 0.04)
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
- Speedup: 24.94x
- Cost: 1.07 -> 0.04
```

---

### 3. `argus watch` — Autonomous Monitoring Daemon
Continuously monitor database query telemetry and auto-validate optimizations:

```bash
poetry run python -m argus.cli watch --interval 60
```

---

## 🏗 Architecture (Hexagonal / Ports & Adapters)

```text
src/argus/
├── domain/                  # Pure Pydantic domain models
│   ├── query.py             # Statements & pg_stat_statements metrics
│   ├── plans.py             # EXPLAIN plan AST structures
│   ├── index.py             # Index definitions & validation results
│   ├── sandbox.py           # Sandbox configurations
│   └── errors.py            # Domain error hierarchy
├── core/                    # Core business logic
│   ├── schema.py            # Catalog introspection & AST table extraction
│   ├── hydrator.py          # Synthetic Twin set-based hydration engine
│   ├── docker_sandbox.py    # Ephemeral Docker container lifecycle manager
│   ├── decision_engine.py   # A/B validation & migration generator
│   ├── observer.py          # Read-only pg_stat_statements telemetry collector
│   ├── analyzer.py          # Plan node traversal & cost analyzer
│   ├── fingerprint.py       # SQL normalization & AST hashing
│   ├── heuristic_brain.py   # Rule-based AST index generator
│   └── gemini_brain.py      # Google Gemini AI brain (gemini-3.5-flash)
└── interfaces/              # User-facing adapters
    ├── cli.py               # CLI entrypoint (audit, check, watch, dashboard)
    ├── explanation_formatter.py # Markdown bottleneck explanation formatter
    └── web/                 # FastAPI Mission Control & REST API
        ├── api.py           # Endpoints (/api/health, /api/audit, /api/check, /api/apply)
        ├── app.py           # FastAPI application factory
        └── static/          # Single-page glassmorphism dashboard (index.html)
```

---

## 🛠 Developer Tooling & Makefile

```bash
make test         # Run unit tests
make integration  # Run live Docker integration tests
make lint         # Run ruff and black formatting checks
make format       # Format codebase with ruff & black
make typecheck    # Run mypy strict type checker (0 errors across 28 source files)
make dashboard    # Launch FastAPI Mission Control on port 8000
make setup-demo   # Setup and seed local PostgreSQL target database
make clean        # Clean test and pycache artifacts
```

---

## 🧪 Test Suite

Argus-PG features a strict test suite with **zero mock dependencies** in production code:

```bash
poetry run pytest tests/ -v
```

* **23 Unit Tests**: Analyzer, decision engine, hydrator, schema catalog introspection, and failure modes.
* **3 Integration Tests**: Live Docker container lifecycle, schema seeding, and A/B latency benchmarking.

---

## 🗺 Roadmap

- [x] Ephemeral Docker Sandbox Lifecycle & Multi-Socket Auto-Discovery
- [x] Automated Catalog Introspection & DDL Extractor
- [x] Synthetic Twin Hydration Engine (Cardinality & Selectivity Matching)
- [x] Plan AST Traversal & `sqlglot` Query Normalization
- [x] Google Gemini AI Brain (`gemini-3.5-flash` with deterministic PII redaction)
- [x] Automated `CREATE INDEX CONCURRENTLY` & Rollback DDL Generator
- [x] FastAPI Mission Control Dashboard & REST API
- [x] Developer Tooling (`Makefile`, `Dockerfile`, `argus.toml`)
- [ ] PR Comment Bot (PyGithub Integration & Webhook Handler)
- [ ] GitHub Actions CI/CD Pipeline

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.
