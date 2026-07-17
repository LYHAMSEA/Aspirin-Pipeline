"""
ChemOps CLI — run protocols from the command line.

Usage:
    python -m chemops.cli run aspirin_synthesis
    python -m chemops.cli run aspirin_synthesis --repeat 3
    python -m chemops.cli sensors
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from chemops.core.orchestrator import Orchestrator, RunStatus
from chemops.protocols.aspirin_synthesis import get_aspirin_protocol
from chemops.sensors.instruments import build_default_registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


PROTOCOLS = {
    "aspirin_synthesis": get_aspirin_protocol,
}


async def run_protocol(protocol_name: str, repeat: int = 1) -> int:
    if protocol_name not in PROTOCOLS:
        logger.error("Unknown protocol '%s'. Available: %s", protocol_name, list(PROTOCOLS))
        return 1

    orchestrator = Orchestrator(reactor_id="reactor-01")
    exit_code = 0

    for i in range(repeat):
        if repeat > 1:
            logger.info("--- Run %d / %d ---", i + 1, repeat)

        steps = PROTOCOLS[protocol_name]()
        run = await orchestrator.execute_protocol(
            protocol_name,
            steps,
            metadata={"cli": True, "iteration": i + 1},
        )

        print(
            json.dumps(
                {
                    "run_id": run.run_id,
                    "status": run.status.value,
                    "duration_s": round(run.duration or 0, 2),
                    "steps": len(run.steps),
                    "final_yield": run.final_yield,
                },
                indent=2,
            )
        )

        if run.status != RunStatus.COMPLETE:
            exit_code = 1

    return exit_code


async def poll_sensors() -> None:
    registry = build_default_registry()
    readings = await registry.poll_all()
    for r in readings:
        print(f"{r.sensor_id:30s} {r.value:10.4f} {r.unit}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="chemops",
        description="ChemOps — autonomous lab orchestration CLI",
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Execute a named protocol")
    run_parser.add_argument(
        "protocol",
        choices=list(PROTOCOLS),
        help="Protocol to execute",
    )
    run_parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        metavar="N",
        help="Number of times to repeat the run (default: 1)",
    )

    sub.add_parser("sensors", help="Poll all sensors and print readings")

    args = parser.parse_args()

    if args.command == "run":
        sys.exit(asyncio.run(run_protocol(args.protocol, args.repeat)))
    elif args.command == "sensors":
        asyncio.run(poll_sensors())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
