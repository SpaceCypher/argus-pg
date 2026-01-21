Here is the updated implementation plan and repository structure, renamed to **`argus-pg`** and switched to the **Google Gemini API**.

### **Repository Name:** `argus-pg`

This structure maintains the **Hexagonal Architecture** (separating logic from interfaces) but updates the dependencies and configuration for Gemini.

```text
argus-pg/
├── .github/                        # GitHub specific automation
│   ├── workflows/
│   │   ├── ci.yml                  # Run tests & linting
│   │   └── release.yml             # Build & publish Docker image
│   └── actions/                    # Custom actions for the PR bot
│
├── deploy/                         # Infrastructure as Code
│   ├── docker-compose.yml          # For running Argus locally
│   ├── helm/                       # For K8s deployment
│   └── terraform/                  # Cloud provisioning (optional)
│
├── docs/                           # Documentation
│   ├── architecture/               # Diagrams (Architecture, Sequence)
│   ├── setup.md
│   └── usage.md
│
├── src/
│   └── argus/                      # Main Package
│       ├── __init__.py
│       ├── config.py               # Pydantic Settings (Loads GEMINI_API_KEY)
│       ├── main.py                 # Application Entrypoint
│       │
│       ├── core/                   # THE BUSINESS LOGIC (No UI code)
│       │   ├── __init__.py
│       │   ├── observer.py         # Connects to Prod DB (pg_stat_statements)
│       │   ├── analyzer.py         # Parses EXPLAIN plans (AST logic)
│       │   ├── brain.py            # Gemini Client & Prompt Logic
│       │   ├── decision.py         # Safety thresholds & verification logic
│       │   └── sandbox.py          # Docker SDK control (The "Lab")
│       │
│       ├── domain/                 # INTERNAL DATA MODELS (Pure Python/Pydantic)
│       │   ├── __init__.py
│       │   ├── query.py            # QueryCandidate, ExecutionPlan schemas
│       │   ├── experiment.py       # ValidationResult, BenchmarkData schemas
│       │   └── migrations.py       # MigrationFile schema
│       │
│       ├── interfaces/             # THE ADAPTERS (Inputs/Outputs)
│       │   ├── __init__.py
│       │   ├── cli/                # INTERFACE 1: CLI (Typer)
│       │   │   ├── __init__.py
│       │   │   ├── app.py          # Main CLI entry point
│       │   │   ├── commands.py     # 'audit', 'check' commands
│       │   │   └── formatter.py    # Rich library table rendering
│       │   │
│       │   ├── github/             # INTERFACE 2: PR BOT
│       │   │   ├── __init__.py
│       │   │   ├── bot.py          # PyGithub logic
│       │   │   ├── commenter.py    # Markdown report generation
│       │   │   └── trigger.py      # Webhook parser
│       │   │
│       │   └── web/                # INTERFACE 3: DASHBOARD (FastAPI)
│       │       ├── __init__.py
│       │       ├── api.py          # Backend API
│       │       └── static/         # Frontend assets
│       │
│       └── utils/                  # Shared utilities
│           ├── db.py               # Asyncpg wrappers
│           ├── logger.py           # JSON structured logging
│           └── secrets.py          # PII redaction logic
│
├── tests/                          # Testing Strategy
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures (Docker setup)
│   ├── unit/                       # Fast tests (Mocked Gemini)
│   │   ├── test_analyzer.py
│   │   └── test_brain.py
│   └── integration/                # Slow tests (Real Docker containers)
│       ├── test_sandbox_lifecycle.py
│       └── test_observer_live.py
│
├── .dockerignore
├── .env.example                    # Template for environment variables
├── .gitignore
├── Dockerfile                      # Builds the Argus agent image
├── Makefile                        # Shortcuts (make test, make run)
├── poetry.lock                     # Dependency lock file
├── pyproject.toml                  # Python project config & deps
└── README.md                       # The "Sales Pitch"

```

### **Updated Configuration Files**

#### **1. `pyproject.toml` (Dependencies)**

*Replaced `openai` with `google-generativeai`.*

```toml
[tool.poetry.dependencies]
python = "^3.11"
pydantic = "^2.5"             # Data validation
asyncpg = "^0.29"             # Postgres driver
typer = "^0.9"                # CLI framework
rich = "^13.7"                # Pretty CLI output
docker = "^7.0"               # Docker SDK
sqlglot = "^20.0"             # SQL Parsing
google-generativeai = "^0.3"  # Gemini API Client
fastapi = "^0.109"            # Web Dashboard Backend
uvicorn = "^0.27"             # Web Server
pygithub = "^2.1"             # GitHub API
tenacity = "^8.2"             # Retry logic

```

#### **2. `.env.example**`

*Updated environment variables for Gemini.*

```bash
# Target Database (Read-Only)
DB_DSN=postgres://argus_user:securepass@prod-db:5432/main

# LLM Configuration (Gemini)
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...     # Your Google AI Studio Key
GEMINI_MODEL=gemini-1.5-flash # Recommended for speed/cost

# Sandbox Configuration
SANDBOX_IMAGE=postgres:15-alpine
DOCKER_HOST=unix:///var/run/docker.sock

```

#### **3. `src/argus/core/brain.py` (Conceptual Update)**

*How the logic changes to use Gemini.*

```python
import google.generativeai as genai
from argus.config import settings

class Brain:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def hypothesize_index(self, schema: str, query: str) -> list[str]:
        prompt = f"""
        You are a PostgreSQL Expert.
        Given Schema: {schema}
        Given Query: {query}
        Generate 3 valid CREATE INDEX statements to optimize this query.
        Return strictly JSON.
        """
        response = self.model.generate_content(prompt)
        # Parse Gemini response...
        return parsed_indexes

```