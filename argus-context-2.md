# Project Specification: Database Index Tuning Agent (Autonomous DBA)

**Role:** Staff Backend Engineer & Technical Project Manager
**Status:** Approved for Implementation
**Version:** 1.0.0
**Owner:** [Your Name]

---

## 1. Project Goals & Non-Goals

### 1.1 Explicit Goals

* **Automated Bottleneck Detection:** Continuously identify high-cost SQL queries (specifically `Seq Scans` and `Bitmap Heap Scans`) causing latency, without human oversight.
* **Empirical Validation:** Mathematically prove that a proposed index improves performance (e.g., "reduces execution time by >40%") in an isolated environment before suggesting it to a human.
* **Infrastructure-as-Code (IaC) Output:** Produce actionable, copy-pasteable migration artifacts (SQL files or ORM migrations), not just conversational advice.
* **Production Safety:** Ensure zero risk of data loss or performance degradation on production databases. The agent never writes to production.

### 1.2 Explicit Non-Goals

* **No Multi-Database Support:** This version supports **PostgreSQL 15+** only. MySQL, Oracle, and Mongo are out of scope.
* **No Query Rewriting:** We do not rewrite inefficient application code (e.g., fixing N+1 loops). We only optimize the database schema (indexes) to support the existing queries.
* **No Automatic Production Writes:** The agent will **never** execute `CREATE INDEX` on the production database. It creates Pull Requests.
* **No Natural Language Chat:** This is not a chatbot. There is no "chat window." The interface is strictly metrics, logs, CLI, and PR comments.

---

## 2. System Overview (End-to-End)

The Database Index Tuning Agent is a **vertical infrastructure agent** designed to solve "Database Drift"—the inevitable degradation of query performance as data volume grows and code changes.

### How it works:

1. **Observe:** It sits alongside the production database (as a sidecar or bastion job) and polls internal statistics (`pg_stat_statements`) to find queries that are statistically slow and frequent.
2. **Orient:** It analyzes the execution plan (`EXPLAIN`) to determine *why* the query is slow (e.g., scanning 5 million rows to find 3).
3. **Hypothesize:** It uses an LLM to generate candidate index strategies based on the schema and query structure.
4. **Validate:** It spins up a temporary **Dockerized PostgreSQL instance**, replicates the schema, generates synthetic data, and runs A/B benchmarks (Before Index vs. After Index).
5. **Act:** If (and only if) the validation proves a significant speedup, it acts:
* **Proactive Mode:** Posts a comment on the GitHub Pull Request blocking the bad code.
* **Reactive Mode:** Opens a new Pull Request with a migration file to fix the existing production lag.



### Users:

* **Backend Engineers:** Receive immediate feedback on PRs when they write unoptimized queries.
* **SREs/DBAs:** Use the CLI/Dashboard to audit overall database health and approve generated migrations.

---

## 3. Architecture Overview

The system uses a **Control Plane / Worker** architecture to decouple decision-making from execution and ensure safety.

### 3.1 Logical Components

1. **The Observer (Telemetry):** A lightweight collector that polls Production. **Trust Boundary:** Read-Only.
2. **The Brain (Control Plane):** The decision engine. Parses logic, manages state, calls the LLM. **Trust Boundary:** No DB Access.
3. **The Lab (Validation Plane):** An isolated environment running Docker. **Trust Boundary:** Root access to *ephemeral* containers only.
4. **The Actuator (Interface):** The API client for GitHub/Slack.

### 3.2 Failure Isolation

* **Sandbox Crash:** If the validation container crashes (OOM), it is simply discarded. Production is untouched.
* **LLM Hallucination:** If the LLM generates invalid SQL, the Sandbox validation fails (Syntax Error), and the suggestion is discarded silently.
* **Connection Loss:** The agent is stateless between runs. It simply retries on the next schedule.

---

## 4. Detailed Component Design

### 4.1 Observer (The Listener)

* **Purpose:** Identify candidates for optimization without adding load.
* **Inputs:** `pg_stat_statements` view, `pg_class` (table metadata).
* **Logic:**
* Polls every X minutes.
* Filters: `total_exec_time > Threshold`, `calls > Threshold`.
* **Crucial Heuristic:** Joins with table stats. Ignores queries on "Small Tables" (< 1000 pages) where Seq Scans are preferred by the planner.


* **Output:** `SlowQueryCandidate` object (Query Text, Frequency, Mean Time).

### 4.2 Query Analyzer (The Filter)

* **Purpose:** Filter out queries that cannot be fixed by indexes (e.g., lock contention, network latency).
* **Logic:**
* Runs `EXPLAIN (FORMAT JSON)` on the candidate query.
* Parses the JSON tree.
* **Accepts:** Node types `Seq Scan`, `Bitmap Heap Scan`.
* **Rejects:** Node types `Index Scan` (already indexed), `Hash Join` (complex join issues often need rewriting, not just indexing).


* **Why:** Saves money on LLM tokens and compute by failing fast.

### 4.3 LLM Hypothesis Generator

* **Purpose:** Generate syntactically correct index candidates.
* **Inputs:** Schema (DDL), Query SQL, Execution Plan JSON.
* **Internal Logic:**
* Prompt: "Given table schema X and query Y, provide 3 PostgreSQL index definitions that optimize the filtering/sorting columns. Output strictly JSON."


* **Output:** List of strings: `["CREATE INDEX idx_a ON users(email)", ...]`.

### 4.4 Sandbox Validation Engine (The Lab)

* **Purpose:** Empirically prove performance gains.
* **Logic:**
1. Provision `postgres:15-alpine` container via Docker SDK.
2. Apply `schema.sql` (dumped from prod).
3. **Hydrate:** Insert N rows of synthetic data using `Faker` (mimicking production types).
4. **Benchmark A:** Run Query 5 times. Record P95 latency.
5. **Apply Fix:** Execute `CREATE INDEX...`.
6. **Benchmark B:** Run Query 5 times. Record P95 latency.
7. **Teardown.**


* **Output:** `ValidationResult` (Improvement Factor, Index Size, Confidence).

### 4.5 Decision Engine

* **Purpose:** The final gatekeeper.
* **Logic:**
* IF `Improvement Factor > 2.0x` (100% speedup)
* AND `Index Size < Table Size * 0.5` (Not bloating storage)
* THEN `Action = APPROVE`.
* ELSE `Action = DISCARD`.



### 4.6 Actuation Layer

* **Purpose:** Communicate with humans.
* **Logic:** Formats the `ValidationResult` into a Markdown table for GitHub or a Rich table for the CLI.

---

## 5. Agent Logic & State Machine

The agent follows a strict loop. It is not a continuous stream; it is a job runner.

**State Flow:**

1. **IDLE:** Waiting for trigger.
2. **SCANNING:** Fetching candidates from Observer.
* *Exit:* If list empty → IDLE.


3. **ANALYZING:** Running `EXPLAIN`.
* *Exit:* If optimization potential low → IDLE.


4. **HYPOTHESIZING:** Querying LLM.
5. **VALIDATING:** Spinning up Docker.
* *Error Handling:* If `CREATE INDEX` fails (syntax) → Retry logic (ask LLM to fix syntax) → Fail.


6. **REPORTING:** Posting to GitHub/CLI.
7. **COOLDOWN:** Mark query as "processed" to avoid spamming duplicate PRs.

---

## 6. Data Models & Internal Schemas

We use strict Pydantic models to ensure type safety.

```python
# The fingerprint of a problem
class QueryContext(BaseModel):
    query_id: str             # pg_stat_statements queryid
    normalized_query: str     # SQL with params replaced ($1)
    mean_exec_time: float
    calls_per_minute: float
    table_names: List[str]

# The proof of the solution
class ValidationReport(BaseModel):
    candidate_index_sql: str
    baseline_latency_ms: float
    optimized_latency_ms: float
    improvement_factor: float # e.g., 5.4x
    index_size_mb: float
    is_regression: bool       # Did it get slower?

```

---

## 7. Sandbox & Experimentation Strategy

### 7.1 Why Sandboxing?

LLMs hallucinate. They might suggest indexing a column that doesn't exist, or suggest a partial index that the optimizer ignores. You cannot trust text. You trust code execution.

### 7.2 Strategy: The "Synthetic Twin"

We cannot copy production data (GDPR/Security).

* **Schema:** Exact copy (`pg_dump --schema-only`).
* **Data:** Synthetic.
* We use the `Faker` library.
* If the column is `email`, we generate emails.
* If the column is `status` (ENUM), we pick from valid enum values.
* **Scale:** We don't need millions of rows. We usually generate **10,000 to 50,000 rows**. This is sufficient to trigger the Postgres Optimizer's decision thresholds (switching from Seq Scan to Index Scan).



---

## 8. Interfaces (Critical)

### A. GitHub Pull Request Bot (The Gatekeeper)

* **Trigger:** GitHub Actions (on PR open/update).
* **Logic:** Scans changed code for SQL strings. Runs validation.
* **Output:**
* **Blocking Review:** If a new query performs a Seq Scan on a large table in the Sandbox.
* **Message:** "⚠️ **Performance Risk:** This query performs a Full Table Scan. I verified this in a sandbox. Adding this index reduces latency by 98%."



### B. CLI Tool (The Operator)

* **Command:** `db-agent check --url $DB_URL`
* **Output:**
```text
[?] Scanning for slow queries...
[!] Found 1 candidate: 'SELECT * FROM orders WHERE user_id = ...'
[.] Spawning sandbox...
[+] Baseline: 450ms | Optimized: 12ms | Improvement: 37x
[>] Validated Index: CREATE INDEX idx_orders_user_id ON orders(user_id);

```



### C. Web Dashboard

* **Status:** **OPTIONAL** for MVP.
* **Goal:** A read-only view of "System Health" (Number of missing indexes found over time).

---

## 9. Technology Stack (Justified)

* **Language: Python 3.11+**
* *Why:* Unrivaled ecosystem for DB drivers (`psycopg`, `SQLAlchemy`), Docker control (`docker-py`), and Orchestration (`LangChain`).


* **Database: PostgreSQL 15+**
* *Why:* The target system. Best-in-class stats (`pg_stat_statements`).


* **Sandbox: Docker SDK + Testcontainers**
* *Why:* Standardizes the "clean slate" environment. `Testcontainers` manages port conflicts and cleanup automatically.


* **SQL Parsing: SQLGlot**
* *Why:* Robust AST parsing. Regex is insufficient for complex SQL.


* **LLM: GPT-4o-mini (or Llama-3-8b via Ollama)**
* *Why:* We need *reasoning*, not creativity. Smaller models are faster, cheaper, and sufficient for SQL generation.



---

## 10. Security & Safety Model

1. **Principle of Least Privilege:**
* The **Observer** uses a read-only DB user.
* It *cannot* modify schemas or data in Production.


2. **Safe Index Creation:**
* The Agent *always* suggests `CREATE INDEX CONCURRENTLY`. This prevents locking the table against writes during index creation in production.


3. **Sanitization:**
* Literal values (e.g., `user_id = 'bob@gmail.com'`) are stripped/parameterized before being sent to the LLM API to prevent PII leaks.



---

## 11. Failure Modes & Edge Cases

* **Write-Heavy Tables:** Indexes slow down `INSERT/UPDATE`.
* *Handling:* The agent checks `pg_stat_user_tables` (`n_tup_ins` vs `n_tup_upd`). If the table is write-heavy (>90% writes), it suppresses the suggestion or warns the user.


* **Disk Space Exhaustion:**
* *Handling:* The agent estimates index size. If `Index Size > 50% Table Size`, it flags the suggestion as "High Storage Cost".


* **False Positives:**
* *Handling:* The Sandbox acts as the filter. If the "Optimized" run is not significantly faster than the "Baseline" run (due to low cardinality or planner choice), the suggestion is silently dropped.



---

## 12. Phased Implementation Plan

### Phase 0: Prerequisites (Days 1-2)

* Set up local Postgres with `pg_stat_statements`.
* Set up Docker Engine.
* Repo scaffolding (Python + Poetry).

### Phase 1: The Observer (Week 1)

* **Deliverable:** `observer.py`
* **Goal:** Connect to DB, fetch top 10 slow queries, print to console.
* **Exclusion:** No analysis, no LLM.

### Phase 2: The Sandbox (Week 2)

* **Deliverable:** `lab.py`
* **Goal:** Input a SQL schema string + Query. Spin up Docker. Run query. Return time.
* **Key Tech:** `Faker` for data generation.

### Phase 3: The Brain (Week 3)

* **Deliverable:** `agent.py`
* **Goal:** Connect Observer to Lab via LLM.
* **Flow:** Fetch Slow Query -> Ask LLM for Index -> Test in Lab -> Print Result.

### Phase 4: The Interface (Week 4)

* **Deliverable:** CLI Tool & PR Commenter script.
* **Goal:** Polish the output. Make it look professional (`rich` tables).

### Phase 5: Hardening (Week 5)

* **Deliverable:** Tests, Docs, Edge case handling (Write-heavy check).

---

## 13. Evaluation & Success Metrics

* **Metric 1: Validation Rate.** (What % of LLM suggestions are proven valid? Target: >60%).
* **Metric 2: Latency Reduction.** (Average speedup of validated queries. Target: >50%).
* **Metric 3: Safety.** (Number of times the agent broke the sandbox or leaked PII. Target: 0).

---

**What the README says:**
"An autonomous infrastructure agent that detects database performance regression, experimentally validates fixes in ephemeral containers, and provides IaC-ready solutions."

---

## 15. Common Misinterpretations (Anti-Bullshit)

* **"It's just an LLM wrapper."**
* **Defense:** No. The LLM is a small utility component (Hypothesis Generator). The core complexity and value lie in the **Sandbox Validation Engine** (Systems Engineering) which provides deterministic proof of value. An LLM wrapper guesses; this agent proves.


* **"Why not use a SaaS tool?"**
* **Defense:** SaaS tools (DataDog/NewRelic) *show* you the slow query. They don't *fix* it, and they certainly don't spin up sandboxes to *test* the fix. This agent closes the loop between Observability and Action.


* **"Is it safe?"**
* **Defense:** Yes. It uses a Read-Only connection to production and validates all changes in a totally isolated, ephemeral Docker container. It never executes writes on the live database.