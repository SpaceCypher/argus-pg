.PHONY: help install test unit integration lint format typecheck run-dashboard demo setup-demo clean

help:
	@echo "Argus-PG Development Commands"
	@echo "-----------------------------"
	@echo "make install      - Install dependencies with Poetry"
	@echo "make test         - Run unit tests"
	@echo "make integration  - Run integration tests (requires Docker daemon)"
	@echo "make lint         - Run ruff and black check"
	@echo "make format       - Format code with ruff and black"
	@echo "make typecheck    - Run mypy type checker"
	@echo "make dashboard    - Start FastAPI web Mission Control on port 8000"
	@echo "make setup-demo   - Setup demo database with 50k unindexed rows"
	@echo "make demo         - Alias for setup-demo"
	@echo "make clean        - Clean pycache and test caches"

install:
	poetry install

test:
	poetry run pytest tests/unit/ -v

integration:
	poetry run pytest tests/integration/ -v

lint:
	poetry run ruff check .
	poetry run black --check .

format:
	poetry run ruff check --fix .
	poetry run black .

typecheck:
	poetry run mypy

dashboard:
	poetry run python -m argus.cli dashboard --host 127.0.0.1 --port 8000 --reload

setup-demo:
	poetry run python scripts/setup_demo.py

demo: setup-demo

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
