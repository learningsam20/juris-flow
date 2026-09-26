# Contributing

## Git workflow

- **Single protected default branch:** `main`. All changes land via pull requests.
- **Feature branches:** create short-lived branches off `main`
  (`fix/`, `feat/`, `chore/`, `docs/` prefixes).
- Run local checks below before opening a PR (no CI workflow in this repo).

## Local checks

```bash
make lint       # ruff check + format check
make typecheck  # mypy
make test       # backend pytest + Rego policy tests
make scan       # pip-audit on backend requirements
(cd frontend && npm run build)
```

## Commit convention

Concise imperative subject line (e.g. `Add review templates and annotations`).
Keep related changes in one commit; do not commit secrets or `.env` files.