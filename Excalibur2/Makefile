# Excalibur Makefile
# Usage: make [target]

.PHONY: help install config connect ssh web attach start stop shell logs clean-docker
.PHONY: dev-install test test-all test-cov lint format typecheck check clean

# Default target
help:
	@echo "Excalibur Commands"
	@echo "==================="
	@echo ""
	@echo "Docker Workflow:"
	@echo "  make install         Build Docker image and install dependencies"
	@echo "  make config          Configure authentication (interactive)"
	@echo "  make connect         Start container and connect over SSH"
	@echo "  make ssh             Connect over SSH to the running container"
	@echo "  make web             Print the local web config UI URL"
	@echo "  make attach          Attach to the container TTY"
	@echo "  make start           Start container in background"
	@echo "  make stop            Stop container (keeps config)"
	@echo "  make shell           Open new shell in running container"
	@echo "  make logs            View container logs"
	@echo "  make clean-docker    Remove everything including config"
	@echo ""
	@echo "Development:"
	@echo "  make dev-install  Install dev dependencies locally"
	@echo "  make test         Run all tests"
	@echo "  make test-cov     Run tests with coverage"
	@echo "  make lint         Run linter (ruff)"
	@echo "  make format       Format code (ruff)"
	@echo "  make typecheck    Run type checker (mypy)"
	@echo "  make check        Run all checks (lint + typecheck)"
	@echo "  make clean        Clean build artifacts"

# ============================================================================
# Docker Workflow
# ============================================================================

install:
	@echo "Installing local dependencies with uv..."
	uv sync
	@echo "Building Excalibur Docker image..."
	docker compose build --no-cache

config:
	@chmod +x scripts/config.sh
	@./scripts/config.sh

# Start the container and connect over SSH (main entry point)
# Handles different auth modes automatically based on .env.auth
connect: start ssh

# Connect to the running container over SSH
ssh:
	@echo "Connecting to Excalibur over SSH..."
	@echo "Default password: $${EXCALIBUR_SSH_PASSWORD:-excalibur}"
	@ssh -o StrictHostKeyChecking=accept-new -p "$${EXCALIBUR_SSH_PORT:-2222}" pentester@127.0.0.1

# Print the web config UI URL
web:
	@echo "Excalibur config UI: http://127.0.0.1:$${EXCALIBUR_WEB_PORT:-8080}"

# Attach to the running container TTY (legacy workflow)
attach:
	@if [ "$$(docker ps -q -f name=excalibur2)" ]; then \
		echo "Attaching to running container..."; \
		docker attach excalibur2; \
	else \
		echo "Starting new container..."; \
		if [ -f .env.auth ]; then \
			docker compose --env-file .env.auth up -d && docker attach excalibur2; \
		else \
			docker compose up -d && docker attach excalibur2; \
		fi; \
	fi

start:
	@if [ -f .env.auth ]; then \
		docker compose --env-file .env.auth up -d; \
	else \
		docker compose up -d; \
	fi

stop:
	docker compose down

shell:
	docker exec -it --user pentester excalibur2 /bin/bash

logs:
	docker compose logs -f

clean-docker:
	docker compose down -v
	docker rmi excalibur2:latest 2>/dev/null || true
	rm -f .env.auth

# ============================================================================
# Local Development
# ============================================================================

dev-install:
	uv sync

# ============================================================================
# Testing
# ============================================================================

test:
	uv run pytest tests/ -v --ignore=tests/docker/

test-all:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ -v --ignore=tests/docker/ --cov=excalibur --cov-report=term-missing --cov-report=html

# ============================================================================
# Code Quality
# ============================================================================

lint:
	uv run ruff check excalibur/ tests/

format:
	uv run ruff format excalibur/ tests/

typecheck:
	uv run mypy excalibur/

check: lint typecheck
	@echo "All checks passed!"

# ============================================================================
# Cleanup
# ============================================================================

clean:
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
