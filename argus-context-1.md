This is a Staff Engineer-level technical specification. It serves as the definitive blueprint for building the **Database Index Tuning Agent**.

This document assumes you are building a tool that must survive the scrutiny of a Senior Systems Engineer or SRE during a technical interview. It prioritizes safety, determinism, and architectural rigor over "AI magic."

---

### 1. Project Goals & Non-Goals

**Explicit Goals:**

* **Automated Detection:** Identify slow queries caused specifically by missing indexes (scanning behavior) without human intervention.
* **Deterministic Validation:** Mathematically prove that a proposed index improves performance in a controlled environment before suggesting it.
* **Infrastructure-as-Code (IaC) Output:** Produce actionable artifacts (migration files, Terraform snippets), not just chat suggestions.
* **Safety First:** Never modify the production database schema automatically. Read-only access to production; write access only to ephemeral sandboxes.

**Explicit Non-Goals (Scope Boundaries):**

* **No Query Rewriting:** We will not attempt to rewrite bad SQL code (e.g., fixing N+1 problems). We only optimize the *schema* (indexes) to support the existing query.
* **No Multi-DB Support:** This is strictly for **PostgreSQL**. Supporting MySQL/Mongo adds abstraction complexity that dilutes the depth of the project.
* **No Production Write Access:** The agent will never run `CREATE INDEX` on production. It generates a Pull Request.
* **No "Natural Language" Interface:** No chat window. The interface is metrics, logs, and Pull Requests.

---

### 2. System Overview

**The "Elevator Pitch" for Engineers:**
This system implements an autonomous OODA loop (Observe, Orient, Decide, Act) for database performance. It acts as a specialized linter that runs in your CI/CD pipeline or as a background worker. It connects to a Postgres instance, identifies expensive sequential scans, spins up a Dockerized replica with sampled data, applies candidate indexes, measures the delta in execution time, and—if the delta meets a success threshold—opens a GitHub PR with the migration.

**Workflow Integration:**

1. **Reactive (Cron):** Runs nightly to catch performance degradation in existing queries due to data growth ("Database Drift").
2. **Proactive (CI/CD):** Runs on every Pull Request to block code that introduces unindexed queries *before* they merge.

---

### 3. Architecture Overview

The system follows a **Control Plane / Worker** pattern to decouple the logic from the execution environment.

**Logical Components:**

1. **The Observer (Telemetry Ingest):**
* **Location:** Runs near the DB (e.g., Bastion host or Sidecar).
* **Trust:** Read-Only access to `pg_stat_statements` and system catalogs.


2. **The Brain (Reasoning Engine):**
* **Location:** Application Server / Lambda.
* **Logic:** Heuristics + LLM. It parses query plans and generates hypotheses.


3. **The Lab (Validation Engine):**
* **Location:** Ephemeral Container Environment (Docker host).
* **Trust:** Full Root access to *its own* throwaway containers.


4. **The Actuator (Interface Layer):**
* **Location:** API Client.
* **Logic:** Formats results into PRs, Slack alerts, or CLI tables.



**Failure Isolation:**

* If **The Lab** crashes (OOM), it does not affect Production.
* If **The Brain** hallucinates invalid SQL, **The Lab** catches the syntax error and discards it.
* If **The Observer** loses connection, the system simply sleeps.

---

### 4. Detailed Component Design

#### **A. Observer (The Listener)**

* **Purpose:** Efficiently extract "problem queries" without adding load to the DB.
* **Inputs:** Database credentials, `pg_stat_statements`.
* **Internal Logic:**
* Queries `pg_stat_statements` filtering by `total_exec_time > X` and `calls > Y`.
* **Crucial Heuristic:** It joins with `pg_class` to check table size. It ignores small tables (<1000 rows) where seq scans are actually faster than index scans.


* **Outputs:** A list of `QueryContext` objects (Query SQL, Frequency, Mean Time, Table Schema).

#### **B. Query Analyzer (The Filter)**

* **Purpose:** Determine *why* a query is slow to avoid wasting tokens on non-indexable issues (e.g., locking, network I/O).
* **Logic:**
* Runs `EXPLAIN (FORMAT JSON)` on the query.
* Parses the JSON tree looking for specific node types: `Seq Scan`, `Bitmap Heap Scan` (with lossy blocks).
* **Filter:** If the plan shows `Index Scan` but it's still slow, the agent skips it (this project focuses on *missing* indexes, not tuning existing ones).



#### **C. LLM Hypothesis Generator (The Architect)**

* **Purpose:** Generate candidates. "Given this query and schema, what index might help?"
* **Inputs:** Schema (DDL), Query, Execution Plan.
* **Internal Logic (Prompt Engineering):**
* Do not ask "Fix this."
* Ask: "Generate 3 PostgreSQL index definitions (B-Tree, GIN, or Composite) that target the filtering columns in this query. Output strictly valid SQL."


* **Outputs:** List of strings: `["CREATE INDEX idx_a ON t(col1)", "CREATE INDEX idx_b ON t(col1, col2)"]`.

#### **D. Sandbox Validation Engine (The Arbiter of Truth)**

* **Purpose:** Empirically test the hypothesis.
* **Internal Logic:**
1. Start `postgres:15-alpine` container via Docker SDK.
2. Apply `schema.sql` (from production dump).
3. **Data Sampling:** Insert synthetic data or a masked subset of real data. *Note: For the MVP, generating synthetic data using Python's `Faker` library that matches the schema types is safer and easier than sampling production.*
4. **Baseline Run:** Execute query, record `execution_time`.
5. **Experiment Run:** Execute `CREATE INDEX...`, then execute query, record `execution_time`.
6. **Teardown:** Kill container.


* **Output:** `BenchmarkResult` (Baseline ms, Experiment ms, Size of Index MB).

---

### 5. Agent Logic & State Machine

The agent is a State Machine, not a linear script. This allows for retries and error handling.

**States:**

1. **IDLE:** Waiting for trigger (Cron or PR).
2. **SCANNING:** Fetching from `pg_stat_statements`.
3. **ANALYZING:** running `EXPLAIN`, filtering non-indexable queries.
4. **HYPOTHESIZING:** LLM generation.
5. **VALIDATING:** Spinning up Docker containers.
* *Transition:* If `CREATE INDEX` fails (syntax error) -> Return to HYPOTHESIZING (Feedback loop).
* *Transition:* If Speedup < 10% -> Mark as "Ineffective", Log, and Stop.


6. **REPORTING:** Generating artifacts.

---

### 6. Data Models & Schemas

You need structured objects to pass data between components. Use **Pydantic** models.

```python
class QueryFingerprint(BaseModel):
    query_id: str
    sql_text: str
    tables_involved: List[str]
    mean_exec_time_ms: float
    calls_per_minute: int

class ExperimentResult(BaseModel):
    index_def: str
    baseline_latency_ms: float
    optimized_latency_ms: float
    improvement_factor: float  # e.g., 5.2x
    index_size_mb: float
    is_valid: bool # True if improvement > threshold

```

---

### 7. Sandbox & Experimentation Strategy

This is the hardest part to get right. How do you simulate a 100GB database in a Docker container?

**The Strategy: Structural Similarity, Not Data Parity.**
Indexes work based on cardinality and selectivity. You don't need *real* data; you need data with similar *statistical properties*.

**The "Faker" Approach (Recommended for MVP):**

* If the query is `SELECT * FROM users WHERE country = 'US'`, the optimizer needs to know that 'US' is 10% of the rows, not 100%.
* **Implementation:**
* The Agent inspects the query literals (`'US'`).
* The Agent generates 10,000 dummy rows.
* It ensures 1,000 rows have `country='US'` and 9,000 have random values.
* This forces the Postgres optimizer to behave realistically (choosing an index scan over a seq scan).



---

### 8. Interfaces

#### **A. GitHub PR Bot**

* **Trigger:** GitHub Action hook on `pull_request`.
* **Action:**
* Parses changed files for `.sql` or code strings matching SQL patterns.
* Runs the validation logic.


* **Output:**
* **Blocker:** If the new query performs a Seq Scan on a large table in the sandbox.
* **Comment:** "⚠️ New query detected on table `orders`. Estimated latency: 500ms. Suggestion: Add migration `CREATE INDEX...` (Verified speedup: 40x)."



#### **B. CLI (The Operator Tool)**

* **Command:** `db-agent inspect --url postgres://... --minutes 60`
* **Output (Rich Table):**
```text
| ID    | Table  | Latency | Recommendation                  | Validated? |
|-------|--------|---------|---------------------------------|------------|
| a1b2  | users  | 450ms   | CREATE INDEX idx_u_email...     | ✅ (12ms)  |
| c3d4  | logs   | 1200ms  | CREATE INDEX idx_l_time...      | ❌ (No imp)|

```



---

### 9. Tech Stack (Justified)

* **Language: Python 3.11+**
* *Why:* Unbeatable ecosystem for Data (Pydantic), Database (SQLAlchemy/Psycopg), Docker Control (docker-py), and Orchestration (LangChain/LangGraph).


* **Database: PostgreSQL 15+**
* *Why:* The target system. We need the latest features (`pg_stat_statements`, `jsonb` logs).


* **Sandbox: Docker Engine + Testcontainers**
* *Why:* `Testcontainers` is a library specifically designed to spin up disposable databases for testing. It handles port mapping and cleanup automatically.


* **SQL Parsing: SQLGlot**
* *Why:* Regex is insufficient for parsing nested SQL queries. SQLGlot creates an Abstract Syntax Tree (AST) allowing precise extraction of table names and WHERE clauses.


* **LLM: GPT-4o-mini or Llama-3-8b (via Ollama)**
* *Why:* We need "Reasoning" capabilities to understand query plans, but we don't need creative writing. Small, smart models are cheaper and faster.



---

### 10. Security & Safety Considerations

* **Principle of Least Privilege:**
* The **Observer** connects to Production with a `READ ONLY` user. It cannot modify data.


* **Sandbox Isolation:**
* The **Lab** never connects to Production. It uses a local container.


* **PII Redaction:**
* The system must strip literals (e.g., specific email addresses) from queries before sending them to an external LLM (GEMINI). Use parameterized queries in logs.



---

### 11. Failure Modes & Edge Cases

* **The "Write Heavy" Trap:** Adding an index speeds up Reads but slows down Writes.
* *Mitigation:* The agent checks `pg_stat_user_tables` for the ratio of Updates vs Selects. If a table is write-heavy (90% writes), it suppresses index suggestions or adds a warning.


* **Hallucinated Columns:** The LLM suggests indexing a column that doesn't exist.
* *Mitigation:* The Sandbox execution will fail with "Column not found." The agent catches this exception and discards the suggestion.


* **Disk Space:** Indexes take space.
* *Mitigation:* The "Experiment Result" includes the size of the index (MB) so the human can decide if it's worth the cost.



---

### 12. MVP Phased Execution Plan

**Phase 1: The Observer (Week 1)**

* **Goal:** Read-only visibility.
* **Deliverable:** Python script that connects to a local DB, enables `pg_stat_statements`, and prints the top 5 slowest queries.

**Phase 2: The Lab (Week 2)**

* **Goal:** Infrastructure orchestration.
* **Deliverable:** Script that accepts a SQL string, spins up a Docker Postgres, applies a schema, runs the query, and times it.

**Phase 3: The Brain (Week 3)**

* **Goal:** Closing the loop.
* **Deliverable:** Connect Phase 1 to Phase 2 via the LLM. Identify slow query -> Generate Index -> Test in Docker -> Print Result.

**Phase 4: The Interface (Week 4)**

* **Goal:** Usability.
* **Deliverable:** Wrap it in a CLI tool (`click` or `typer`) and produce a GitHub PR format.

---

### 13. Evaluation & Success Metrics

* **Precision:** What % of suggested indexes actually pass the validation step? (Target: >80%).
* **Impact:** Average latency reduction on validated queries (Target: >50% reduction).
* **Safety:** Zero incidents of the agent attempting to write to production.

---



**The README:**
Must clearly state: "This tool uses Docker to safely validate database indexes in an ephemeral environment before suggesting them." This sentence alone separates you from 90% of applicants.

---

### 15. Common Misinterpretations (Anti-Bullshit)

* **"Is this just asking ChatGPT for SQL?"**
* *Defense:* "No. LLMs are terrible at performance tuning because they don't know the data distribution. This system uses the LLM only for *hypothesis generation*. The core value is the **Sandbox Validation Engine** which empirically proves the performance gain."


* **"How does it handle real data privacy?"**
* *Defense:* "It doesn't use real data. It replicates the *schema* and uses statistical sampling/faking to mimic cardinality. We test logic, not raw data."



---
