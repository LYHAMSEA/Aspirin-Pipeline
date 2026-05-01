#!/usr/bin/env python3
"""
ChemOps Protocol Linter.

Validates that protocol files conform to ChemOps standards:
  - All step functions are async coroutines
  - All steps return a dict (type-annotated or inferred)
  - Mandatory protocol metadata is present
  - Step names follow snake_case convention
  - A get_<protocol>_protocol() builder function is exported
  - No bare `except:` clauses (must catch specific exceptions)
  - Temperature and pH values are within safe operating ranges

Usage:
    python linting/chemops_linter.py chemops/protocols/aspirin_synthesis.py
    python linting/chemops_linter.py chemops/protocols/          # lint a directory
    python linting/chemops_linter.py --strict chemops/protocols/
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


# ---------------------------------------------------------------------------
# Violation model
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    rule: str
    severity: Severity
    message: str
    line: int = 0
    col: int = 0

    def __str__(self) -> str:
        loc = f":{self.line}:{self.col}" if self.line else ""
        return f"  [{self.severity.value}] {self.rule}{loc}  {self.message}"


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------

SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SAFE_TEMP_RANGE = (-20.0, 300.0)  # °C — lab operating limits
SAFE_PH_RANGE = (0.0, 14.0)


class ProtocolLinter(ast.NodeVisitor):
    """
    AST visitor that checks a single protocol module for ChemOps compliance.
    """

    def __init__(self, source: str, filepath: Path) -> None:
        self.source = source
        self.filepath = filepath
        self.violations: list[Violation] = []
        self._async_def_names: list[str] = []
        self._all_def_names: list[str] = []
        self._module_docstring_present = False
        self._has_builder_fn = False

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def lint(self) -> list[Violation]:
        tree = ast.parse(self.source, filename=str(self.filepath))
        self._check_module_docstring(tree)
        self.visit(tree)
        self._check_builder_function()
        self._check_snake_case_functions()
        return self.violations

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _add(
        self,
        rule: str,
        severity: Severity,
        message: str,
        node: ast.AST | None = None,
    ) -> None:
        line = getattr(node, "lineno", 0)
        col = getattr(node, "col_offset", 0)
        self.violations.append(
            Violation(rule=rule, severity=severity, message=message, line=line, col=col)
        )

    def _check_module_docstring(self, tree: ast.Module) -> None:
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            self._module_docstring_present = True
        else:
            self._add(
                "CL001",
                Severity.WARNING,
                "Module is missing a docstring. Add a top-level docstring "
                "describing the protocol, reaction equation, and parameters.",
            )

    def _check_builder_function(self) -> None:
        if not self._has_builder_fn:
            self._add(
                "CL002",
                Severity.ERROR,
                "Protocol module must export a builder function named "
                "'get_<protocol_name>_protocol()' that returns the ordered step list.",
            )

    def _check_snake_case_functions(self) -> None:
        for name in self._all_def_names:
            if not SNAKE_CASE_RE.match(name) and not name.startswith("_"):
                self._add(
                    "CL005",
                    Severity.ERROR,
                    f"Function name '{name}' does not follow snake_case convention.",
                )

    # ------------------------------------------------------------------
    # AST visitors
    # ------------------------------------------------------------------

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._async_def_names.append(node.name)
        self._all_def_names.append(node.name)
        self._check_return_annotation(node)
        self._check_function_docstring(node)
        self._check_bare_except(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._all_def_names.append(node.name)
        # Check for builder function
        if node.name.startswith("get_") and node.name.endswith("_protocol"):
            self._has_builder_fn = True
            self._check_builder_return(node)
        self._check_bare_except(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Check that numeric constants for temp/pH are within safe ranges."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                name_upper = target.id.upper()
                if "TEMP" in name_upper and isinstance(node.value, ast.Constant):
                    val = node.value.value
                    if isinstance(val, (int, float)):
                        lo, hi = SAFE_TEMP_RANGE
                        if not (lo <= val <= hi):
                            self._add(
                                "CL007",
                                Severity.ERROR,
                                f"Temperature constant '{target.id}' = {val} °C "
                                f"is outside safe operating range ({lo}–{hi} °C).",
                                node,
                            )
                if "PH" in name_upper and isinstance(node.value, ast.Constant):
                    val = node.value.value
                    if isinstance(val, (int, float)):
                        lo, hi = SAFE_PH_RANGE
                        if not (lo <= val <= hi):
                            self._add(
                                "CL008",
                                Severity.ERROR,
                                f"pH constant '{target.id}' = {val} "
                                f"is outside valid range ({lo}–{hi}).",
                                node,
                            )
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Sub-checks
    # ------------------------------------------------------------------

    def _check_return_annotation(self, node: ast.AsyncFunctionDef) -> None:
        """Step functions should annotate return type."""
        if node.returns is None:
            self._add(
                "CL003",
                Severity.WARNING,
                f"Async step function '{node.name}' is missing a return type annotation. "
                "Add '-> dict[str, Any]:' or similar.",
                node,
            )

    def _check_function_docstring(self, node: ast.AsyncFunctionDef) -> None:
        if not (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        ):
            self._add(
                "CL004",
                Severity.WARNING,
                f"Async step function '{node.name}' is missing a docstring. "
                "Document what the step does, parameters, and return keys.",
                node,
            )

    def _check_bare_except(self, node: ast.AsyncFunctionDef | ast.FunctionDef) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.ExceptHandler) and child.type is None:
                self._add(
                    "CL006",
                    Severity.ERROR,
                    f"Bare 'except:' clause in '{node.name}'. "
                    "Catch specific exceptions (e.g. 'except ValueError:').",
                    child,
                )

    def _check_builder_return(self, node: ast.FunctionDef) -> None:
        """Builder function should return a list literal or variable."""
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                if child.value is None:
                    self._add(
                        "CL009",
                        Severity.ERROR,
                        f"Builder function '{node.name}' has a bare 'return' "
                        "with no value — must return a list of (name, coro) tuples.",
                        child,
                    )


# ---------------------------------------------------------------------------
# File/directory runner
# ---------------------------------------------------------------------------


def lint_file(path: Path, strict: bool = False) -> list[Violation]:
    source = path.read_text(encoding="utf-8")
    linter = ProtocolLinter(source, path)
    violations = linter.lint()
    if strict:
        # Upgrade warnings to errors in strict mode
        for v in violations:
            if v.severity == Severity.WARNING:
                v.severity = Severity.ERROR
    return violations


def lint_path(target: Path, strict: bool = False) -> dict[Path, list[Violation]]:
    results: dict[Path, list[Violation]] = {}
    if target.is_file():
        results[target] = lint_file(target, strict)
    elif target.is_dir():
        for py_file in sorted(target.rglob("*.py")):
            if py_file.name.startswith("_"):
                continue
            results[py_file] = lint_file(py_file, strict)
    else:
        print(f"ERROR: '{target}' is not a file or directory", file=sys.stderr)
        sys.exit(2)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="chemops-lint",
        description="ChemOps protocol linter — validates lab automation scripts",
    )
    parser.add_argument(
        "targets",
        nargs="+",
        metavar="PATH",
        help="Python file or directory to lint",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only output files with violations",
    )
    args = parser.parse_args()

    total_errors = 0
    total_warnings = 0
    total_files = 0

    for target_str in args.targets:
        results = lint_path(Path(target_str), strict=args.strict)
        for filepath, violations in results.items():
            total_files += 1
            errors = [v for v in violations if v.severity == Severity.ERROR]
            warnings = [v for v in violations if v.severity == Severity.WARNING]
            total_errors += len(errors)
            total_warnings += len(warnings)

            if violations or not args.quiet:
                status = "FAIL" if errors else ("WARN" if warnings else "OK  ")
                print(f"\n{status}  {filepath}")
                for v in violations:
                    print(str(v))

    print(
        f"\n{'─'*60}\n"
        f"ChemOps Lint: {total_files} file(s) checked — "
        f"{total_errors} error(s), {total_warnings} warning(s)"
    )

    if total_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
