# Changelog

All notable changes to this project will be documented in this file.

## [v0.1.0-mvp] - 2026-01-22

### Added
- **Core Engine**: `DockerSandbox` for ephemeral Postgres instances using `docker-py` and `psycopg`.
- **Observation**: Read-only `Observer` adapter for `pg_stat_statements` analysis.
- **Brains**:
    - `HeuristicBrain`: Rule-based index suggester (Seq Scans + Filters).
    - `GeminiBrain`: LLM-based suggester using `google-genai` SDK (Supports `gemini-1.5*`, `gemini-2.0*`, `gemini-3*`).
- **CLI**:
    - `argus audit`: Lists top resource-intensive queries from a running DB.
    - `argus check`: Validates specific queries against a sandbox.
    - `argus watch`: Daemon mode for continuous optimization.
- **Validation**:
    - Automated cost measurement (baseline vs. optimized).
    - Data persistence via Docker commit/build.
    - Strict `mypy` typing and `ruff` linting.

### Fixed
- **Docker Integration**: Resolved `DOCKER_HOST` connectivity issues on macOS/Colima.
- **Gemini API**: Migrated from deprecated `google.generativeai` to modern `google-genai` client, handling `429` quotas gracefully.
- **Heuristics**: Improved column extraction logic to ignore string literals and SQL keywords.
