# ⚗️ ChemOps

> **Git-Driven CI/CD Pipeline for Autonomous Laboratory Orchestration**
>
> A production-grade framework for treating chemical synthesis protocols as code — versioned, linted, tested, and deployed through a modern DevOps pipeline.

[![CI](https://github.com/your-org/chemops/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/chemops/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/your-org/chemops/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/chemops)
[![Python](https://img.shields.io/badge/python-3.11%20|%203.12-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ghcr.io%2Fyour--org%2Fchemops-blue?logo=docker)](https://github.com/your-org/chemops/pkgs/container/chemops)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Case Study: Aspirin Synthesis](#case-study-aspirin-synthesis)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local development](#local-development)
  - [Docker stack](#docker-stack)
- [Project Structure](#project-structure)
- [Protocol Development](#protocol-development)
  - [Writing a protocol](#writing-a-protocol)
  - [ChemOps linter](#chemops-linter)
- [CI/CD Pipeline](#cicd-pipeline)
- [Monitoring](#monitoring)
  - [Prometheus metrics](#prometheus-metrics)
  - [Grafana dashboards](#grafana-dashboards)
  - [Alerting rules](#alerting-rules)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

ChemOps applies software engineering discipline to laboratory automation. Every synthesis protocol is a Python module, every experiment is a traceable run, and every instrument reading is a Prometheus metric. The result: reproducible chemistry, observable pipelines, and zero "it worked on my bench" surprises.

```
Git push → CI lint + test → Docker build → Security scan → Deploy → Live Grafana dashboard
```

**Core ideas:**

- **Protocols as code.** Synthesis procedures are async Python functions — version-controlled, diff-able, and peer-reviewed like any other software.
- **Continuous integration for chemistry.** A custom protocol linter (`chemops-lint`) enforces safety standards before code ever reaches a reactor.
- **Observability first.** Every step, temperature reading, pH measurement, and product yield is scraped by Prometheus and visualised in Grafana in real time.
- **Containerised and reproducible.** The entire stack (API + monitoring) runs with a single `docker compose up`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        GitHub                               │
│  ┌──────────┐   push/PR   ┌──────────────────────────────┐  │
│  │ Protocol │ ──────────► │  GitHub Actions CI/CD        │  │
│  │  .py     │             │  lint → test → build → deploy│  │
│  └──────────┘             └──────────────┬───────────────┘  │
└─────────────────────────────────────────┼───────────────────┘
                                          │ docker push
                             ┌────────────▼────────────┐
                             │      Container Runtime   │
                             │                          │
                             │  ┌────────────────────┐  │
                             │  │   ChemOps API       │  │
                             │  │   (FastAPI)         │  │
                             │  │   :8000             │  │
                             │  └────────┬───────────┘  │
                             │           │               │
                             │  ┌────────▼───────────┐  │
                             │  │   Orchestrator      │  │
                             │  │   Sensor Registry   │  │
                             │  └────────┬───────────┘  │
                             │           │ /metrics      │
                             │  ┌────────▼───────────┐  │
                             │  │   Prometheus :9090  │  │
                             │  └────────┬───────────┘  │
                             │           │               │
                             │  ┌────────▼───────────┐  │
                             │  │   Grafana :3000     │  │
                             │  └────────────────────┘  │
                             └─────────────────────────-┘
```

---

## Case Study: Aspirin Synthesis

ChemOps ships with a complete aspirin (acetylsalicylic acid) synthesis protocol as its reference implementation.

**Reaction:**
```
C₇H₆O₃  +  (CH₃CO)₂O  →  C₉H₈O₄  +  CH₃COOH
Salicylic acid + Acetic anhydride → Acetylsalicylic acid + Acetic acid
```

**Protocol steps (9 total):**

| # | Step | Duration | Key output |
|---|------|----------|------------|
| 1 | `prepare_reagents` | ~2 s | Mass/volume confirmation |
| 2 | `charge_reactor` | ~3 s | Reactor loaded |
| 3 | `heat_to_reaction_temperature` | ~7 s | 85 °C confirmed |
| 4 | `hold_at_temperature` | ~5 s | 15-min readings logged |
| 5 | `quench_reaction` | ~2 s | Precipitation observed |
| 6 | `vacuum_filter` | ~2 s | Crude mass recorded |
| 7 | `recrystallise` | ~3 s | Purity ≥ 97.5% |
| 8 | `dry_and_weigh` | ~2 s | Final yield % |
| 9 | `quality_control` | ~2 s | MP + FeCl₃ test |

**Expected yield:** 78–90% of theoretical (16.5 g from 14.0 g salicylic acid)
**QC specification:** Melting point 135–136 °C, FeCl₃ test negative

---

## Getting Started

### Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.11 |
| Docker | 24.0 |
| Docker Compose | 2.24 |
| Git | 2.40 |

### Local development

```bash
# 1. Clone the repository
git clone https://github.com/your-org/chemops.git
cd chemops

# 2. Set up virtual environment and install all dependencies
./scripts/dev.sh setup
source .venv/bin/activate

# 3. Run the full lint suite
./scripts/dev.sh lint

# 4. Run unit tests
./scripts/dev.sh test

# 5. Start the API in dev mode (auto-reload)
./scripts/dev.sh run
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

**Run the aspirin protocol via CLI:**

```bash
# Single run
python -m chemops.cli run aspirin_synthesis

# Three consecutive runs
python -m chemops.cli run aspirin_synthesis --repeat 3

# Poll all sensors
python -m chemops.cli sensors
```

**Trigger a run via HTTP:**

```bash
curl -X POST http://localhost:8000/runs \
     -H "Content-Type: application/json" \
     -d '{"protocol": "aspirin_synthesis", "metadata": {"batch": "B001"}}'
```

### Docker stack

Start the full monitoring stack (API + Prometheus + Grafana) with one command:

```bash
./scripts/dev.sh docker-up
```

| Service | URL | Credentials |
|---------|-----|-------------|
| ChemOps API | http://localhost:8000 | — |
| API Docs | http://localhost:8000/docs | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / chemops_dev |

Tear down:
```bash
./scripts/dev.sh docker-down
```

---

## Project Structure

```
chemops/
├── .github/
│   ├── workflows/
│   │   └── ci.yml                  # Full CI/CD pipeline (lint→test→build→deploy)
│   ├── dependabot.yml              # Automated dependency updates
│   └── PULL_REQUEST_TEMPLATE.md
│
├── chemops/                        # Main package
│   ├── __init__.py
│   ├── api.py                      # FastAPI application + REST endpoints
│   ├── cli.py                      # Command-line interface
│   ├── core/
│   │   └── orchestrator.py         # Async protocol runner + Prometheus metrics
│   ├── protocols/
│   │   └── aspirin_synthesis.py    # Aspirin synthesis — 9 async steps
│   ├── sensors/
│   │   └── instruments.py          # Sensor abstraction (temp/pH/pressure/balance)
│   └── utils/
│
├── tests/
│   ├── unit/
│   │   ├── test_orchestrator.py    # 8 orchestrator unit tests
│   │   ├── test_aspirin_protocol.py# 10 protocol step unit tests
│   │   └── test_sensors.py         # 7 sensor unit tests
│   └── integration/
│       └── test_full_run.py        # End-to-end protocol integration tests
│
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml          # Scrape config
│   │   └── alerts.yml              # 11 alerting rules (temp/pH/yield/API)
│   └── grafana/
│       ├── dashboards/
│       │   └── chemops_main.json   # Pre-built Grafana dashboard
│       └── provisioning/           # Auto-provisioned datasource + dashboard
│
├── linting/
│   └── chemops_linter.py           # Custom AST-based protocol linter
│
├── scripts/
│   └── dev.sh                      # Developer convenience commands
│
├── Dockerfile                      # Multi-stage build (builder → runtime)
├── docker-compose.yml              # Full stack: API + Prometheus + Grafana
├── pyproject.toml                  # Single source of truth: deps + ruff + mypy
└── README.md
```

---

## Protocol Development

### Writing a protocol

Every protocol is a Python module in `chemops/protocols/`. It must:

1. Have a module-level docstring including the reaction equation
2. Export a `get_<name>_protocol()` function returning `list[tuple[str, AsyncCallable]]`
3. Implement each step as an `async def` function returning `dict[str, Any]`
4. Include docstrings on every step function
5. Use type annotations on all return values

**Minimal example:**

```python
"""
My Reaction — X + Y → Z

Reaction: X + Y → Z + byproduct
"""
from __future__ import annotations
import asyncio
from typing import Any

async def prepare_reagents() -> dict[str, Any]:
    """Weigh and transfer X and Y into a clean flask."""
    await asyncio.sleep(1)
    return {"mass_x_g": 10.0, "volume_y_ml": 15.0, "temperature": 22.0}

async def run_reaction() -> dict[str, Any]:
    """Heat mixture to 60 °C and hold for 10 minutes."""
    await asyncio.sleep(2)
    return {"temperature": 60.0, "ph": 5.5, "yield_pct": 85.0}

def get_my_reaction_protocol() -> list[tuple[str, Any]]:
    return [
        ("prepare_reagents", prepare_reagents),
        ("run_reaction", run_reaction),
    ]
```

**Reserved return keys** (automatically picked up by the orchestrator and pushed to Prometheus):

| Key | Type | Prometheus metric |
|-----|------|-------------------|
| `temperature` | `float` | `chemops_reactor_temperature_celsius` |
| `ph` | `float` | `chemops_reactor_ph` |
| `yield_pct` | `float` | `chemops_product_yield_percent` |

### ChemOps linter

The custom protocol linter (`linting/chemops_linter.py`) performs static analysis using Python's AST. It runs as part of CI and can be used locally:

```bash
# Lint a single protocol file
python linting/chemops_linter.py chemops/protocols/aspirin_synthesis.py

# Lint all protocols (strict mode — warnings become errors)
python linting/chemops_linter.py chemops/protocols/ --strict
```

**Linting rules:**

| Rule | Severity | Description |
|------|----------|-------------|
| CL001 | WARNING | Missing module docstring |
| CL002 | ERROR | Missing `get_<name>_protocol()` builder function |
| CL003 | WARNING | Async step missing return type annotation |
| CL004 | WARNING | Async step missing docstring |
| CL005 | ERROR | Function name not in `snake_case` |
| CL006 | ERROR | Bare `except:` clause (must catch specific exceptions) |
| CL007 | ERROR | Temperature constant outside safe range (−20 to 300 °C) |
| CL008 | ERROR | pH constant outside valid range (0–14) |
| CL009 | ERROR | Builder function returns nothing |

---

## CI/CD Pipeline

The GitHub Actions pipeline (`.github/workflows/ci.yml`) runs on every push and pull request:

```
┌────────┐    ┌──────┐    ┌───────┐    ┌──────────┐    ┌──────────────┐
│  Lint  │ →  │ Test │ →  │ Build │ →  │ Security │ →  │    Deploy    │
│        │    │      │    │ image │    │   scan   │    │  (main only) │
│ ruff   │    │ py   │    │       │    │  Trivy   │    │              │
│ mypy   │    │ 3.11 │    │ GHCR  │    │  SARIF   │    │  SSH deploy  │
│ bandit │    │ 3.12 │    │ push  │    │  upload  │    │  → staging   │
│ chem-  │    │      │    │ multi │    │          │    │              │
│ lint   │    │ cov  │    │ arch  │    │          │    │              │
└────────┘    └──────┘    └───────┘    └──────────┘    └──────────────┘
```

**Branch strategy:**

| Branch | Triggers | Deploys |
|--------|----------|---------|
| `develop` | Lint + Test + Build | No deployment |
| `main` | Full pipeline | Staging auto-deploy |
| `v*.*.*` tag | Full pipeline | GitHub Release created |
| Pull Request | Lint + Test + Build (no push) | — |

**Adding secrets for deployment:**
```
STAGING_HOST       SSH hostname of staging server
STAGING_USER       SSH username
STAGING_SSH_KEY    Private key (Ed25519 recommended)
```

---

## Monitoring

### Prometheus metrics

All metrics are exposed at `GET /metrics` and scraped every 10 seconds.

| Metric | Type | Description |
|--------|------|-------------|
| `chemops_active_runs` | Gauge | Currently running protocol executions |
| `chemops_reactor_temperature_celsius{reactor_id}` | Gauge | Live reactor temperature |
| `chemops_reactor_ph{reactor_id}` | Gauge | Live reactor pH |
| `chemops_step_duration_seconds{protocol, step}` | Histogram | Step execution time distribution |
| `chemops_steps_total{protocol, step, status}` | Counter | Step completions by status |
| `chemops_protocol_runs_total{protocol, outcome}` | Counter | Run completions by outcome |
| `chemops_product_yield_percent{protocol}` | Summary | Product yield distribution |
| `chemops_sensor_reading{sensor_id, unit}` | Gauge | Raw sensor values |
| `chemops_sensor_last_seen_timestamp{sensor_id}` | Gauge | Last successful sensor read |

### Grafana dashboards

The `chemops_main` dashboard (auto-provisioned) includes:

- **Stat panels:** active runs, total success/fail counts
- **Gauge panels:** live temperature (0–300 °C) and pH (0–14) with threshold colouring
- **Time series:** temperature and pH trends over the last hour
- **Step rate chart:** success/failure rates per protocol step
- **Yield trend:** running product yield percentage
- **Heatmap:** step duration distribution

Access: `http://localhost:3000` → login with `admin / chemops_dev` → ChemOps folder.

### Alerting rules

Eleven alerting rules are pre-configured in `monitoring/prometheus/alerts.yml`:

**Reactor safety:**
- `ReactorOvertemperature` — critical if T > 250 °C for 1 min
- `ReactorTemperatureHigh` — warning if T > 200 °C for 5 min
- `ReactorTemperatureUnderRange` — warning if T < −10 °C for 2 min
- `ReactorPHCritical` — critical if pH < 1 or pH > 13 for 2 min
- `ReactorPHWarning` — warning if pH < 1.5 or pH > 12 for 5 min

**Pipeline health:**
- `TooManyActiveRuns` — warning if > 5 concurrent runs for 2 min
- `HighStepFailureRate` — warning if failure rate > 10% over 10 min
- `LowProductYield` — warning if yield < 60%

**Infrastructure:**
- `ChemOpsAPIDown` — critical if Prometheus cannot reach API for 1 min
- `SensorStale` — warning if any sensor silent for > 2 min

---

## API Reference

Full interactive documentation: `http://localhost:8000/docs`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Liveness probe → `{"status": "ok"}` |
| `GET` | `/readyz` | Readiness probe → reactor ID |
| `POST` | `/runs` | Trigger a protocol run |
| `GET` | `/runs` | List all runs |
| `GET` | `/runs/{run_id}` | Fetch a specific run |
| `GET` | `/sensors` | Latest reading from all sensors |
| `GET` | `/metrics` | Prometheus scrape endpoint |

**POST /runs — request body:**
```json
{
  "protocol": "aspirin_synthesis",
  "metadata": {
    "batch_id": "B-2024-001",
    "operator": "Dr. Okonkwo",
    "notes": "Validation run #1"
  }
}
```

**Run response:**
```json
{
  "run_id": "3f8a1c2d-...",
  "protocol": "aspirin_synthesis",
  "status": "complete",
  "started_at": 1717000000.0,
  "completed_at": 1717000035.2,
  "final_yield": null,
  "steps": [
    {
      "name": "prepare_reagents",
      "status": "complete",
      "duration_s": 2.014,
      "data": { "salicylic_acid_g": 14.032, "acetic_anhydride_ml": 20.07 },
      "error": null
    }
  ]
}
```

---

## Testing

```bash
# Unit tests only (fast, no external dependencies)
pytest tests/unit/ -v

# Integration tests (full protocol execution)
pytest tests/integration/ -v -m integration

# All tests with coverage report
pytest --cov=chemops --cov-report=html --cov-report=term-missing

# Open coverage report
open htmlcov/index.html

# Run only a specific test
pytest tests/unit/test_orchestrator.py::test_run_stops_on_failure -v
```

**Test matrix:**

| Suite | Tests | Focus |
|-------|-------|-------|
| `tests/unit/test_orchestrator.py` | 8 | Orchestrator FSM, hooks, error propagation |
| `tests/unit/test_aspirin_protocol.py` | 10 | Individual step outputs and invariants |
| `tests/unit/test_sensors.py` | 7 | Sensor reading, clamping, registry |
| `tests/integration/test_full_run.py` | 3 | End-to-end protocol execution |

Coverage threshold: **80%** (enforced in CI via `pytest-cov`).

---

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CHEMOPS_REACTOR_ID` | `reactor-01` | Reactor identifier (appears in metrics labels) |
| `CHEMOPS_LOG_LEVEL` | `info` | Uvicorn log level (`debug`, `info`, `warning`, `error`) |
| `PYTHONUNBUFFERED` | `1` | Stream logs immediately (recommended in Docker) |

**Production Grafana:** change `GF_SECURITY_ADMIN_PASSWORD` in `docker-compose.yml` or inject via environment before deploying.

---

## Contributing

1. Fork the repository and create a branch: `git checkout -b feature/your-protocol`
2. Install dev dependencies: `./scripts/dev.sh setup`
3. Write your protocol in `chemops/protocols/`
4. Add unit tests in `tests/unit/`
5. Run the full lint suite: `./scripts/dev.sh lint`
6. Run tests: `./scripts/dev.sh test-all`
7. Open a pull request using the provided template

**New protocol checklist:**
- [ ] Module docstring with reaction equation
- [ ] All steps are `async def` with return type annotations
- [ ] All steps have docstrings
- [ ] `get_<name>_protocol()` builder function exported
- [ ] `chemops-lint --strict` passes
- [ ] Unit tests cover every step function
- [ ] Integration test added for the full protocol run

---

## License

MIT — see [LICENSE](LICENSE).

---

> *"The best experiment is the one that runs the same way every time."*
>
> ChemOps was conceived as a research PhD project exploring the intersection of pharmaceutical technology, industrial chemistry, and DevOps engineering. The aspirin synthesis serves as a reproducible, well-understood benchmark for validating the orchestration framework.
