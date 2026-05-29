# Week 1 Plan

## Goal

Stabilize the local engineering baseline so the team can reliably run development,
database migrations, backend tests, and frontend lint checks before continuing
MVP feature work.

## Scope

- Fix local startup entrypoints.
- Align Alembic migrations with current ORM models.
- Make backend tests runnable from the documented commands.
- Make frontend lint non-interactive and runnable in local/CI environments.

## Tasks

1. Repair `make dev` by restoring the expected dev compose override and keeping
   the agreed local ports (`5000`, `5001`, `5432`, `6379`).
2. Add a follow-up migration for `watchlists.screen_params_json` and
   `watchlists.auto_refresh` so the schema matches the application models.
3. Fix Python test import resolution so `cd backend && uv run pytest tests/ -v`
   works without manual `PYTHONPATH` setup.
4. Replace the interactive `next lint` flow with a checked-in ESLint setup that
   works under Turborepo.
5. Re-run the baseline commands and capture any remaining gaps.

## Definition Of Done

- `make dev` no longer references missing files.
- `cd backend && uv run alembic upgrade head` succeeds on a fresh database.
- `cd backend && uv run pytest tests/ -q` completes without import errors.
- `cd frontend && pnpm lint` runs without prompting for ESLint initialization.

## Notes

- This week intentionally avoids adding new product features.
- The target is a dependable foundation for week 2 MVP delivery work.
