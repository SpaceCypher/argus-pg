# Argus: Project Guardrails & Intent Definition

## 1. PROJECT IDENTITY (CANONICAL)

Argus is a deterministic infrastructure agent designed to eliminate PostgreSQL database drift. It operates as an automated specialized site reliability engineer (SRE) that continuously monitors query performance, identifies regression caused by missing indexes, and mathematically proves the efficacy of fixes in ephemeral sandbox environments. It is a piece of backend plumbing, similar to a linter or a CI/CD runner, not a creative assistant or generative AI demo. Its value is derived entirely from its reliability, safety, and lack of noise.

## 2. EXPLICIT NON-GOALS

* **No Code Rewriting:** Argus does not attempt to rewrite application code (e.g., fixing N+1 queries, removing logic from views). It only optimizes the database schema to support existing query patterns.
* **No Multi-Database Support:** Argus does not support MySQL, MongoDB, or Oracle. It is strictly optimized for PostgreSQL internals.
* **No Chat Interface:** Argus does not converse with users. It reports data via standard engineering channels (Pull Requests, CLI tables, Logs).
* **No Automatic Writes:** Argus never executes write operations (`CREATE`, `DROP`, `ALTER`) against a production database.
* **No "General Advice":** Argus does not provide generic tuning tips (e.g., "Vacuum your DB"). It only suggests specific, validated indexes.
If no LLM provider is configured, Argus skips hypothesis generation and exits without action.
## 3. HARD CONSTRAINTS (NON-NEGOTIABLE)

1. **Read-Only Production Access:** The component connecting to the live database (The Observer) must strictly utilize a read-only credential with no write privileges.
2. **Sandbox Isolation:** Validation logic must **always** occur in a disposable, network-isolated container. Validation must never run against a production, staging, or shared development database.
3. **Concurrent Creation Only:** All proposed index migrations must use `CREATE INDEX CONCURRENTLY` to prevent table locking in production.
4. **Privacy by Design:** Literal values (PII) found in query logs must be parameterized or redacted before being transmitted to any third-party inference service (LLM).
5. **Deterministic Proof:** A suggestion cannot be surfaced to a user unless it has passed a successful A/B benchmark in the sandbox. "Thinking" an index works is insufficient; proving it works is mandatory.

## 4. USER & WORKFLOW ASSUMPTIONS

* **Primary Users:** Backend Engineers (via GitHub PRs) and Site Reliability Engineers (via CLI).
* **Workflow Integration:**
* **Proactive:** Users encounter Argus as a "blocking check" or "warning bot" in their Pull Request when they introduce unoptimized SQL.
* **Reactive:** SREs use Argus via CLI to investigate and resolve alerting production latency.


* **Not Built For:** Product Managers, Data Analysts, or non-technical stakeholders. The output assumes knowledge of SQL and schema migration workflows.

## 5. FAILURE PHILOSOPHY

* **Silence is Golden:** If Argus cannot find a missing index, or if the proposed index does not significantly improve performance in the sandbox, Argus must remain silent. It is better to miss an optimization than to spam engineers with ineffective noise.
* **False Positives are Fatal:** A single incorrect suggestion (e.g., an index that degrades write performance without helping reads) destroys trust in the tool. We prioritize high precision (correctness) over high recall (finding every possible fix).
* **Fail Safe:** If any component (Docker, LLM, DB Connection) fails, the system must degrade gracefully (log the error and exit) rather than attempting to guess or bypass safety checks.

## 6. DECISION AUTHORITY BOUNDARIES

* **Argus MAY:**
* Decide which queries are "slow" based on configured thresholds.
* Decide which index candidates to test in the sandbox.
* Decide if a test result counts as a "success" based on math.
* Draft a Pull Request containing SQL code.


* **Argus MUST NEVER:**
* Merge its own Pull Request.
* Execute DDL (Data Definition Language) on a non-sandbox environment.
* Decide to ignore PII redaction rules for "better context."



## 7. ANTI-MISINTERPRETATION NOTES

| ❌ Misinterpretation | ✅ Correct Framing |
| --- | --- |
| "Argus is a chatbot for SQL." | Argus is a background worker that runs experiments. |
| "Argus uses AI to write indexes." | Argus uses AI to *generate hypotheses*; it uses the Postgres engine to *validate* them. |
| "Argus fixes bad code." | Argus patches the database schema to handle the code as written. |
| "The LLM is the brain." | The LLM is just a parser/generator. The *Sandbox* is the source of truth. |
| "It's okay to guess if the sandbox fails." | If the sandbox fails, the workflow aborts. No guessing allowed. |