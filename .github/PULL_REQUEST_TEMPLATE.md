## Summary

<!-- What does this PR do? -->

## Type of change

- [ ] Bug fix
- [ ] New feature / protocol
- [ ] Refactor
- [ ] Documentation
- [ ] CI/CD / infrastructure

## Protocol changes (if applicable)

- [ ] New protocol added
- [ ] Existing protocol modified — step count: **before → after**
- [ ] Safety parameters changed (temp/pH limits)
- [ ] ChemOps linter passes: `python linting/chemops_linter.py chemops/protocols/ --strict`

## Testing

- [ ] Unit tests added / updated
- [ ] Integration tests pass locally
- [ ] `pytest --cov=chemops` coverage ≥ 80%

## Checklist

- [ ] `ruff check` passes
- [ ] `mypy chemops/` passes
- [ ] `bandit -r chemops/` passes
- [ ] Docker image builds: `docker build -t chemops:test .`
- [ ] README updated if API surface changed
