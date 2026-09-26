# Contributing

## Git workflow

- **Single protected default branch:** `main`. All changes land via pull requests.
- **Featuring branches:** create short-lived branches off `main`
  (`fix/`, `feat/`, `chore/`, `docs/` prefixes).
- **CI gates (must be green before merge):** ruff lint + format, mypy, backend
  pytest suite, Rego policy tests, frontend production build, dependency
  vulnerability scan.
- **Direct pushes to `main` are blocked** in the repo settings; the CI workflow
  in `.github/workflows/ci.yml` runs on every push and pull request.

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