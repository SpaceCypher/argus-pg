# Project Blueprint: Argus

**Codename:** Argus
**Role:** Autonomous Database Performance & Indexing Engine
**Tagline:** "The watchman that fixes database drift before it wakes you up."

---

## 1. Executive Summary

**Argus** is a vertical infrastructure agent designed to eliminate "Database Drift"—the silent degradation of query performance that occurs as data grows and code evolves. Unlike standard monitoring tools that merely *alert* you to slow queries, Argus acts as an autonomous Junior DBA. It detects high-latency queries, hypothesizes missing indexes, **mathematically validates fixes in an ephemeral sandbox**, and opens GitHub Pull Requests with ready-to-merge migrations.

**Key Technical Differentiator:** Argus does not rely on LLM hallucinations. It uses a **"Sandbox-First"** architecture where every AI suggestion is proven in a Dockerized environment before a human ever sees it.

---

## 2. System Architecture

The system operates on a strictly decoupled **Control Plane / Worker** model to ensure production safety.

### 2.1 The Core Components

1. **The Eye (Observer):** A lightweight telemetry collector that polls `pg_stat_statements` on the production database. It uses a read-only connection to identify candidates (high latency, sequential scans).
2. **The Cortex (Analysis Engine):** The logic layer. It parses SQL execution plans (`EXPLAIN`), filters out non-indexable problems (like network locks), and uses an LLM (Llama 3 or GPT-4o) to generate candidate index strategies.
3. **The Lab (Validation Engine):** The "Crown Jewel." A specialized worker that manages ephemeral Docker containers. It spins up a fresh Postgres instance, replicates the schema, generates synthetic data, and runs A/B benchmarks (Baseline vs. Optimization).
4. **The Hand (Actuator):** The interface layer. It formats validated results into CLI tables or GitHub Pull Request comments.

---

## 3. The Autonomous Loop (OODA)

Argus executes a four-step OODA Loop (Observe, Orient, Decide, Act).

### Step 1: Observe (Telemetry Ingestion)

* **Action:** Argus connects to Production (Read-Only).
* **Query:** Scans `pg_stat_statements` for queries where:
* `mean_exec_time` > 100ms (configurable threshold).
* `calls` > 10 per minute.


* **Heuristic Filter:** It joins `pg_class` to check table sizes. It ignores small tables (<1000 pages) where a Sequential Scan is actually faster than an Index Scan.
* **Output:** A list of `QueryCandidate` objects.

### Step 2: Orient (Root Cause Analysis)

* **Action:** Argus runs `EXPLAIN (FORMAT JSON)` on the candidate query.
* **Logic:** It parses the JSON tree to find the "Costliest Node."
* *If Node == `Seq Scan` on Table X:* **PROCEED.**
* *If Node == `Index Scan`:* **ABORT** (It's already indexed, the issue is likely data skew or application logic).


* **Output:** An `AnalyzedQuery` object containing the specific table and column causing the bottleneck.

### Step 3: Decide (Hypothesis & Validation)

This is where Argus separates itself from simple "GPT Wrappers."

1. **Hypothesis:** The LLM is given the Query and Schema. It is prompted to generate 3 valid `CREATE INDEX` statements.
2. **The Sandbox Test:**
* **Spin Up:** Argus uses `docker-py` to launch `postgres:15-alpine`.
* **Hydrate:** It applies the production schema (`pg_dump -s`). It uses `Faker` to generate 50k rows of synthetic data that mimics the production types (e.g., timestamps, emails, enums).
* **Benchmark A (Baseline):** Run the query 5 times. Average latency: **450ms**.
* **Apply Fix:** Run `CREATE INDEX idx_users_email...` inside the container.
* **Benchmark B (Optimized):** Run the query 5 times. Average latency: **12ms**.


3. **Verdict:**
* *Improvement Factor:* 37.5x.
* *Result:* **VALID.**



### Step 4: Act (Reporting)

* **Action:** Argus constructs a report.
* **Output:** A GitHub PR comment or CLI output showing the mathematical proof.

---

## 4. Technical Specifications

### Tech Stack

* **Core Logic:** Python 3.11+ (Type-hinted, Pydantic for data validation).
* **Database:** PostgreSQL 15+ (Production target & Sandbox target).
* **Infrastructure Orchestration:** Docker SDK for Python (to control containers).
* **SQL Parsing:** `sqlglot` (for robust AST parsing of SQL).
* **LLM Integration:** GEMINI API  or Ollama (Llama-3).
* **Interfaces:** `Typer` (CLI), `PyGithub` (GitHub Integration).

### Data Models (Pydantic)

```python
class ValidationResult(BaseModel):
    query_id: str
    suggested_index: str
    baseline_latency: float  # ms
    optimized_latency: float # ms
    improvement_factor: float
    index_size_mb: float
    is_safe: bool            # Checks for locking issues

```

---

## 5. The "Secret Sauce": Sandbox Strategy

The most common question in interviews will be: *"How do you simulate production data?"*

**The Strategy: Structural Similarity.**
You do not need real user data to prove an index works. You need **Cardinality** and **Selectivity**.

1. **Schema Replication:** We copy the DDL exactly. If production has a composite primary key, the sandbox has it too.
2. **Synthetic Data Generation (Faker):**
* Argus analyzes the query predicates.
* *Query:* `SELECT * FROM orders WHERE status = 'PENDING'`.
* *Generation Strategy:* Argus sees an ENUM column. It generates 50,000 rows. It ensures 'PENDING' is present in ~10% of rows (random distribution) to force the database planner to make a realistic choice.


3. **Why this works:** Indexes are about algorithmic complexity ( vs ). Even on dummy data, a missing index will show a Sequential Scan, and adding one will show an Index Scan. The *relative* speedup (e.g., "50x faster") holds true regardless of the data content.

---

## 6. Interfaces

### A. The "Gatekeeper" (GitHub PR Bot)

* **Trigger:** When a developer opens a PR with changes to `.sql` files or backend code.
* **Behavior:** Argus scans the new code. If it finds a query that lacks an index in the sandbox, it comments:
> **⚠️ Performance Warning**
> Argus detected a full table scan in `users.py`.
> * **Sandbox Result:** 500ms (Seq Scan) -> 15ms (Index Scan).
> * **Recommendation:** Add the following migration:
> ```sql
> CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
> 
> ```
> 
> 
> 
> 



### B. The "Mission Control" (CLI)

For the SRE managing the system.

* **Command:** `argus audit --target prod --verbose`
* **Output:** A rich terminal table.
```text
| Status | Table   | Query Hash | Latency | Speedup | Action |
|--------|---------|------------|---------|---------|--------|
| ✅     | payments| a1b2c3     | 1.2s    | 40x     | PR #12 |
| ❌     | logs    | x9y8z7     | 300ms   | 1.1x    | Ignore |

```



---

## 7. Safety Protocols

**Rule 1: The Blood-Brain Barrier**
The "Lab" (Sandbox) is physically isolated from "The Eye" (Production). There is no code path that allows the Sandbox to execute commands on Production.

**Rule 2: Read-Only Access**
Argus connects to production with a user role that has `CONNECT` and `SELECT` privileges only. It cannot `DROP`, `ALTER`, or `INSERT`.

**Rule 3: Concurrent Creation**
All index suggestions explicitly use `CREATE INDEX CONCURRENTLY`. This instruction tells Postgres to build the index without locking the table against writes, preventing downtime if a human blindly copies the suggestion.

---

## 8. Implementation Roadmap (5 Weeks)

* **Week 1: The Eye.** Build `observer.py`. Connect to a local Postgres, enable `pg_stat_statements`, and reliably identify slow queries.
* **Week 2: The Lab.** Build `sandbox.py`. Use `docker-py` to spin up a container, ingest a schema string, and run a dummy query.
* **Week 3: The Brain.** Connect the Observer to the Lab. Fetch query -> Generate Hypothesis (LLM) -> Validate in Lab.
* **Week 4: The Hand.** Build the CLI using `Typer` and the GitHub integration.
* **Week 5: Hardening.** Add unit tests, write the `README`, and record the demo video.

---

## 9. Resume Positioning

**Project Title:** Argus: Autonomous Database Performance & Indexing Engine
**Bullet Points:**

* Designed a vertical infrastructure agent that eliminates database drift by autonomously detecting and fixing missing indexes in PostgreSQL.
* Engineered a **"Sandbox-First" validation architecture** using Docker and Python, reducing false-positive optimizations by mathematically proving performance gains (e.g., 400ms → 12ms) in ephemeral containers.
* Built a custom SQL parsing engine (AST) to filter non-indexable queries, reducing LLM token costs by 60%.
* Integrated with GitHub Actions to block performance regressions in CI/CD, enforcing a "Performance-as-Code" standard.