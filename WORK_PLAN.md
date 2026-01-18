# Argus-PG Implementation Plan

## Phase 0: System & Tooling Setup
*Goal: Prepare the environment.*

- **0.1. Environment Init**: Verify dependencies, create tracking files, setup .venv and poetry.

## Phase 1: Domain Layer (Foundation & Vocabulary)
*Goal: Establish strict Pydantic models to serve as the shared vocabulary. No side effects allow.*

- **1.1. Project Setup**: Initialize repository structure, dependency management (Poetry/Pipenv), and linter configuration.
- **1.2. Query & Plan Models**: Define strict types for SQL queries, EXPLAIN plans, and Postgres statistics.
- **1.3. Index & Migration Models**: Define types for Index definitions, DDL statements, and validation suggestions.
- **1.4. Sandbox Models**: Define configuration schemata for Sandboxes and structure of Validation Results.
- **1.5. Error Hierarchy**: Define domain-specific exceptions to cleanly separate infrastructure failures from logical rejections.

## Phase 2: Core Layer - Sandbox Engine (The Truth)
*Goal: Build the deterministic validation engine. This is the heart of the system.*

- **2.1. Abstract Sandbox Interface**: Define the contract for sandbox environments (Ports).
- **2.2. Docker Client Adapter**: Implement the low-level Docker control adapter using the Python Docker SDK.
- **2.3. Sandbox Lifecycle**: Implement logic for efficient container provisioning, startup, and teardown.
- **2.4. Seeding Mechanism**: Implement schema extraction from source and rehydration into the sandbox container.
- **2.5. Validation Logic**: Implement the mechanics of running a query, measuring cost/time, applying an index, and re-measuring.

## Phase 3: Core Layer - Observation & Analysis (The Input)
*Goal: Enable the system to see what is happening in the target database.*

- **3.1. DB Connection Adapter**: Implement async Database adapter (likely `asyncpg`) for read-only operations.
- **3.2. Observer Component**: Implement querying `pg_stat_statements` to fetch high-load query candidates.
- **3.3. Analyzer Component**: Implement execution of `EXPLAIN (FORMAT JSON)` and parsing of the resulting plan tree.
- **3.4. Query Fingerprinting**: Implement logic to normalize queries and identify unique patterns.

## Phase 4: Core Layer - Brain & Decision (The Architecture)
*Goal: Integrate the intelligence layer while keeping it strictly optional.*

- **4.1. Abstract Brain Interface**: Define the Port for a Hypothesis Generator.
- **4.2. Heuristic Brain (No-LLM)**: Implement a fallback "Brain" that suggests basic indexes (e.g., on foreign keys) for testing.
- **4.3. Gemini Adapter**: Implement the adapter for Google Gemini API to generate index hypotheses.
- **4.4. Decision Engine**: Implement the logic that compares Sandbox results against thresholds to make final recommendations.

## Phase 5: Interfaces Layer (The Interaction)
*Goal: Expose the system to users via CLI.*

- **5.1. Configuration Loader**: Implement strict parsing of config files (YAML) and environment variables.
- **5.2. CLI Skeleton**: Initialize `Typer` app and define command structure.
- **5.3. Audit Command**: Wiring of Observer -> Analyzer to show current DB state.
- **5.4. Check Command**: specialized workflow for "One-off" validation.
- **5.5. Watch Command**: The main loop logic (Observer -> Brain -> Sandbox -> Report).

## Phase 6: Testing & Validation
*Goal: Verify the system safely.*

- **6.1. Unit Test Suite**: Tests for all Domain models and Core logic (mocked adapters).
- **6.2. Integration Test Suite**: Tests running against a real Docker daemon and a real Postgres instance.
- **6.3. Failure Mode verification**: Verify system behavior when Gemini is down, Docker is full, or DB is locked.
