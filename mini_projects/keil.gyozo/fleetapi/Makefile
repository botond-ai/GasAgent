.PHONY: help install test run clean docker-build docker-up docker-down format lint

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install -r requirements.txt

test:  ## Run tests with coverage
	pytest --cov=. --cov-report=html --cov-report=term-missing

test-unit:  ## Run only unit tests
	pytest -m unit -v

test-watch:  ## Run tests in watch mode
	pytest-watch

run:  ## Run the application
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

run-prod:  ## Run in production mode
	uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

clean:  ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	rm -rf .pytest_cache htmlcov .coverage

format:  ## Format code with black and isort
	black .
	isort .

lint:  ## Run linters
	flake8 .
	mypy .

docker-build:  ## Build Docker image
	docker-compose build

docker-up:  ## Start Docker containers
	docker-compose up -d

docker-down:  ## Stop Docker containers
	docker-compose down

docker-logs:  ## Show Docker logs
	docker-compose logs -f

docker-shell:  ## Open shell in container
	docker-compose exec fleet-api-client bash

example-langgraph:  ## Run LangGraph example
	python langgraph_integration.py

setup-dev:  ## Setup development environment
	cp .env.example .env
	python -m venv venv
	@echo "Now activate the virtual environment:"
	@echo "  source venv/bin/activate  (Linux/Mac)"
	@echo "  venv\\Scripts\\activate  (Windows)"
	@echo "Then run: make install"

check:  ## Run all checks (lint, format-check, test)
	@echo "Running format check..."
	black --check .
	@echo "Running linter..."
	flake8 .
	@echo "Running type check..."
	mypy .
	@echo "Running tests..."
	pytest
	@echo "All checks passed!"
