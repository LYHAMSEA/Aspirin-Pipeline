#!/usr/bin/env bash
# scripts/dev.sh — developer convenience commands
# Usage: ./scripts/dev.sh <command>
set -euo pipefail

CMD=${1:-help}

case "$CMD" in
  setup)
    echo "→ Creating virtual environment..."
    python -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -e ".[dev,lint]"
    echo "✓ Dev environment ready. Activate with: source .venv/bin/activate"
    ;;

  lint)
    echo "→ Running ruff..."
    ruff check chemops/ tests/ --fix
    ruff format chemops/ tests/
    echo "→ Running mypy..."
    mypy chemops/
    echo "→ Running bandit..."
    bandit -r chemops/ -c pyproject.toml
    echo "→ Running ChemOps protocol linter..."
    python linting/chemops_linter.py chemops/protocols/ --strict
    echo "✓ All lint checks passed"
    ;;

  test)
    echo "→ Running unit tests..."
    pytest tests/unit/ -v --cov=chemops --cov-report=term-missing
    ;;

  test-all)
    echo "→ Running all tests (unit + integration)..."
    pytest tests/ -v --cov=chemops --cov-report=term-missing --cov-report=html
    echo "✓ Coverage report: htmlcov/index.html"
    ;;

  run)
    echo "→ Starting ChemOps API (dev mode)..."
    uvicorn chemops.api:app --host 0.0.0.0 --port 8000 --reload --log-level debug
    ;;

  docker-up)
    echo "→ Starting full stack (API + Prometheus + Grafana)..."
    docker compose up --build -d
    echo "✓ Services up:"
    echo "   API:        http://localhost:8000"
    echo "   Metrics:    http://localhost:8000/metrics"
    echo "   Prometheus: http://localhost:9090"
    echo "   Grafana:    http://localhost:3000  (admin / chemops_dev)"
    ;;

  docker-down)
    docker compose down
    echo "✓ All containers stopped"
    ;;

  docker-logs)
    docker compose logs -f chemops-api
    ;;

  protocol-run)
    echo "→ Running aspirin synthesis via CLI..."
    python -m chemops.cli run aspirin_synthesis
    ;;

  sensors)
    echo "→ Polling all sensors..."
    python -m chemops.cli sensors
    ;;

  help|*)
    echo "ChemOps Dev Scripts"
    echo ""
    echo "Usage: ./scripts/dev.sh <command>"
    echo ""
    echo "Commands:"
    echo "  setup          Create .venv and install all dependencies"
    echo "  lint           Run ruff, mypy, bandit, and ChemOps linter"
    echo "  test           Run unit tests with coverage"
    echo "  test-all       Run unit + integration tests"
    echo "  run            Start API server in dev/reload mode"
    echo "  docker-up      Build and start full stack (API + Prometheus + Grafana)"
    echo "  docker-down    Stop all containers"
    echo "  docker-logs    Tail API logs"
    echo "  protocol-run   Execute aspirin synthesis via CLI"
    echo "  sensors        Poll and print all sensor readings"
    ;;
esac
