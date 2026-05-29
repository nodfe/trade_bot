# Engineering Harness

## Purpose

This document is the project-internal engineering discipline for `trade_bot`. It is the single checklist every contributor — human or agent — should consult before opening or merging a PR. The word "Harness" here is *not* an external compliance standard, vendor product, or industry framework; it is shorthand for the in-repo guardrails that keep the admin web, backend API, and bot gateway aligned as the codebase grows. When this document and lived practice diverge, this document is updated first; ad-hoc conventions do not become canon by accident.

The harness is intentionally modest: it codifies what we already expect of ourselves so that decisions are made once, in writing, instead of re-litigated in every review.

---

## Contract-first development

Backend Pydantic v2 schemas in each module's `schemas.py` are the source of truth for what a route accepts and returns. Routes are thin: they parse the request schema, call a service method, and return a response schema.

- Every new HTTP route MUST declare typed request and response models. `response_model=` on the FastAPI decorator is mandatory for non-trivial responses; `dict[str, Any]` return types are not acceptable for product endpoints.
- Frontend hooks under `frontend/packages/hooks` map 1:1 to backend routes. A hook's request/response TypeScript types MUST mirror the backend schema. If a backend schema changes, the corresponding hook is updated in the same PR.
- Reference layout: `backend/app/modules/market_data/{router.py, schemas.py, service.py, repository.py, models.py, tasks.py}` is the canonical module shape. New modules follow it.
- A PR is rejected if a route is added or modified without a corresponding entry in `schemas.py` and without an aligned hook update where a frontend caller exists.

---

## Migrations gate

Database schema is owned by Alembic. Every change to a SQLAlchemy model ships with a matching Alembic revision in the same PR.

- Model files live at `backend/app/modules/<module>/models.py` and `backend/app/models.py`. Revisions live at `backend/migrations/versions/`.
- Generate a revision via `make makemigration msg="short_description"`. Apply with `make migrate`.
- A PR is rejected if any tracked `models.py` is modified without a corresponding new file under `backend/migrations/versions/*.py`.
- Revisions MUST be reviewed for: TimescaleDB hypertable creation/alteration, index changes, default values that require a backfill, and any operation that locks tables in production.
- Down migrations are best-effort but required for destructive changes so a bad rollout can be reversed locally.

---

## Public dependencies only

All third-party dependencies — Python packages, npm packages, Docker base images — MUST resolve from public registries. The approved sources are:

- Python: PyPI (via `uv` / `pyproject.toml`)
- JavaScript: npmjs.org (via `pnpm` workspaces)
- Container images: Docker Hub or GHCR (`ghcr.io`)

Internal mirrors, proprietary feeds, employer-internal package indexes, and private registry URLs are not permitted in `pyproject.toml`, `package.json`, lockfiles, `Dockerfile`s, or `docker-compose*.yml`. This keeps the project portable and reproducible for any contributor on any network. See the P0-A audit notes (recorded in `docs/notes/` once written) for the original review that flagged this rule.

---

## Observability minimum

Every module emits structured logs at well-defined lifecycle points. Today logging is `logging.getLogger(__name__)`; structured logging via `structlog` is being introduced in P0-E. Either way, the *events* below are non-negotiable.

Required log events:

- `sync.start`, `sync.end`, `sync.failure` — for any market_data or watchlist sync entry point (`backend/app/modules/market_data/tasks.py`, `service.py`, and equivalents).
- `provider.fallback` — whenever DataFacade falls back from the primary provider (Tushare) to a secondary (AKShare) under `backend/app/modules/market_data/providers/`.
- `bot.command.invoke`, `bot.command.success`, `bot.command.failure` — emitted at the boundary in `backend/app/modules/bot/commands/`.
- `task.start`, `task.end`, `task.failure` — for every Celery task entrypoint.

Each event MUST carry, at minimum: a stable event name, the relevant identifier (symbol, user, command, task id), and duration where applicable. PII and credentials never appear in logs.

---

## Testing baseline

Backend tests live in `backend/tests/`. The baseline command is:

```
cd backend && uv run pytest tests/ -q
```

This MUST pass on every PR. The repository-level `make test` runs the same suite.

Critical-path coverage rules:

- Any change to `backend/app/modules/market_data/router.py` requires at least one unit test under `backend/tests/unit/` exercising the changed path. See existing `tests/unit/test_market_data_router.py`.
- Any change to `backend/app/modules/watchlist/service.py` requires at least one unit test. See existing `tests/unit/test_watchlist_service.py`.
- Any new bot command handler under `backend/app/modules/bot/commands/` requires at least one unit test for the dispatch + parsing path; the SDK boundary is mocked.
- Tests that touch a real database, Redis, or an external API go under `backend/tests/integration/`. Currently empty — when the first such test lands, it is also the moment to wire `pytest -m integration` into CI separately from the fast unit run.

Frontend tests are TBD until a frontend feature ships with logic worth testing (i.e., not merely page composition). When that happens, the harness adds a Vitest baseline and a smoke Playwright run.

---

## Bot adapter discipline

The bot stack is split into three layers and the layering is enforced by import rules:

- `backend/app/modules/bot/adapters/<platform>/` — owns the SDK. `lark-oapi`, future DingTalk SDK, future Slack SDK, etc., MUST only be imported here.
- `backend/app/modules/bot/commands/` — parses commands, calls services, shapes results. MUST NOT import any platform SDK.
- `backend/app/modules/bot/service.py`, `session/`, `middleware/` — platform-agnostic orchestration. Same restriction.

Adding a new bot platform:

1. Create `backend/app/modules/bot/adapters/<new_platform>/`.
2. Implement the `BotAdapter` ABC defined in `backend/app/modules/bot/adapters/base.py` *fully* — partial adapters are not merged.
3. Translate platform events into the shared command/event types; do not leak platform message objects upward.
4. Register the adapter through the existing wiring in `backend/app/modules/bot/service.py`.

Reviewers reject any PR that imports `lark_oapi` (or another vendor SDK) from `commands/`, `service.py`, or any module outside `bot/adapters/`.

---

## Error envelope

All HTTP responses use the unified error format defined in `backend/app/shared/errors.py`. This module is being introduced in P0-E; once present, it is the only allowed error-shaping surface.

Rules:

- Routes raise typed exceptions; the global exception handler converts them into the envelope.
- Routes do not return `{"error": "..."}` dicts, do not return tuples of `(payload, status)`, and do not call `JSONResponse` with ad-hoc shapes for errors.
- Validation errors from Pydantic are formatted by the same handler so the frontend sees one shape.
- The frontend `packages/api-client` parses this envelope; new error codes are added there alongside the backend change.

---

## Definition of Done

A change is Done only when **all** of the following are true. Missing items mean the PR is not ready, regardless of how complete the code looks.

- [ ] Code implementation merged behind the right module boundary.
- [ ] Alembic migration present if any `models.py` changed.
- [ ] Pydantic request/response schemas present for any new or modified route.
- [ ] Frontend hook in `packages/hooks` updated if the route has a frontend consumer.
- [ ] Unit tests added or updated for critical paths (see Testing baseline).
- [ ] Structured log events emitted for the lifecycle points listed in Observability minimum.
- [ ] Errors returned through the shared envelope (`app/shared/errors.py`).
- [ ] `make test` and `make lint` pass locally.
- [ ] Docs updated: this file, an ADR, or a knowledge-sediment note, when the change is user-facing or architectural.
- [ ] Admin UI and/or bot command updated if the feature is user-facing.

---

## ADR process

Non-trivial architectural decisions are recorded as Architecture Decision Records under `docs/adr/`. Filenames are zero-padded and slugged: `docs/adr/0001-data-facade-fallback-policy.md`, `docs/adr/0002-bot-session-store.md`, etc.

Use this template inline:

```markdown
# ADR NNNN: <title>

Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded by ADR-XXXX

## Context
What forces are in play, what we know today, what constraints exist.

## Decision
The choice we made, in one paragraph. Be specific. Name the alternatives that were rejected and why.

## Consequences
What becomes easier, what becomes harder, what we will need to revisit, and what follow-up work this implies.
```

An ADR is warranted when a decision will be hard to reverse (storage choice, auth model, bot platform contract, data provider strategy) or will be repeatedly questioned otherwise.

---

## Knowledge sediment

Operational knowledge — provider quirks, Feishu caveats, data quality edge cases, runbook steps for common incidents — accumulates in `docs/notes/`, one short markdown file per topic. Suggested examples:

- `docs/notes/tushare-rate-limits.md`
- `docs/notes/akshare-symbol-format.md`
- `docs/notes/feishu-card-update-pitfalls.md`
- `docs/notes/timescale-hypertable-tuning.md`
- `docs/notes/sync-recovery-runbook.md`

Rule: if a contributor learns something the hard way, it is written down in `docs/notes/` in the same PR or in a follow-up landed within a week. This replaces oral tradition and survives team turnover.

---

## Forbidden

These are unconditional. A PR violating any of them is rejected without further discussion:

- Port `8081` anywhere — Docker, dev servers, configs, examples, scripts, tests.
- Dependencies sourced from internal mirrors or private registries.
- Importing a bot platform SDK (e.g., `lark_oapi`) outside `backend/app/modules/bot/adapters/<platform>/`.
- Adding or modifying an HTTP route without Pydantic request/response schemas.
- Modifying a `models.py` without an accompanying Alembic revision in the same PR.
