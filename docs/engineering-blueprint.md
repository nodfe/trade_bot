# trade_bot Engineering Blueprint

## 1. Product North Star

`trade_bot` should become an A-share quantitative analysis platform with three coordinated surfaces:

1. `Admin Web`: a management and analysis console for operators, researchers, and strategy users.
2. `Backend API`: the system of record for market data, analysis tasks, strategies, accounts, and bot-facing workflows.
3. `Bot Gateway`: a unified conversational entry point for multiple bot platforms; Feishu is the first implementation, but the interface must stay platform-agnostic.

The first meaningful milestone is not "full quant platform". It is:

`A user can ingest A-share market data, view it in the admin console, and trigger/query the same core analysis capabilities from Feishu Bot through a shared backend service layer.`

## 2. Architecture Principles

This project should follow a few long-lived principles.

### 2.1 Single Business Core, Multiple Interaction Surfaces

Business capabilities should live in backend application services, not inside Next.js pages or bot handlers.

- Admin uses backend APIs.
- Bot commands call the same backend services.
- Scheduled jobs and async tasks also call the same backend services.

This avoids duplicated logic and keeps admin, API, and bot outputs consistent.

### 2.2 Feature Modules Over Layer-Only Organization

The existing backend direction is correct: feature-based modules under `backend/app/modules/`.

Recommended long-term modules:

- `market_data`: stock master, daily bars, snapshots, news, dragon tiger list, limit-up board
- `analysis`: indicators, factor calculations, scoring, screeners
- `backtest`: strategy definitions, engine orchestration, result storage
- `portfolios`: watchlists, positions, simulated accounts
- `bot`: adapters, commands, middleware, conversation/session state
- `auth`: users, roles, access control, API auth
- `admin`: admin-specific APIs and aggregated dashboard data

### 2.3 Contract-First Integration

Frontend hooks, backend routes, bot commands, and async workers should all align to explicit contracts.

Current repository note:

- `frontend/packages/hooks/src/use-stock-data.ts` expects endpoints such as `/stocks/kline` and `/stocks/{symbol}/quote`.
- The current FastAPI routes expose `/api/v1/market/daily/{code}` and `/stocks`.

This mismatch should be resolved early. Contract drift is one of the fastest ways to create rework.

### 2.4 Async by Default for I/O, Sync by Exception

Continue using:

- FastAPI async endpoints
- SQLAlchemy async engine/session
- async provider/service boundaries
- Celery for long-running, scheduled, or fan-out workloads

### 2.5 Bot Platform Abstraction Must Remain Real

Feishu is only the first adapter. The `BotAdapter` abstraction should remain strict enough that adding DingTalk, WeCom, Telegram, or Slack later does not require rewriting business logic.

The adapter layer should own:

- message/event translation
- card/message rendering primitives
- platform-specific auth and webhook/WebSocket concerns

The command/service layer should own:

- command parsing
- authorization decisions
- analysis execution
- result shaping

## 3. Recommended Target Architecture

### 3.1 High-Level Flow

1. Market data enters via Tushare or AKShare.
2. Backend services normalize and persist data into PostgreSQL/TimescaleDB.
3. Analysis services compute indicators, rankings, and strategy outputs from stored data.
4. Admin UI queries backend APIs for dashboards, screening, and charts.
5. Bot commands trigger the same backend services and return text/cards.
6. Celery handles scheduled sync, heavy analysis, and card update workflows.

### 3.2 Backend Layers

For each mature module, prefer this internal split:

- `router.py`: HTTP contract only
- `schemas.py`: request/response DTOs
- `service.py`: business orchestration
- `repository.py`: persistence and query logic
- `models.py`: ORM models
- `tasks.py`: Celery entry points where needed
- `providers/`: third-party integrations

This is already visible in `market_data` and should be preserved.

### 3.3 Frontend Layers

Frontend should evolve into these layers:

- `apps/admin`: product UI, routes, page composition
- `packages/api-client`: typed fetch client and transport concerns
- `packages/hooks`: TanStack Query hooks aligned to backend contracts
- `packages/ui`: shadcn-based design system primitives and shared A-share widgets
- `packages/charts`: chart wrappers, themes, reusable financial chart adapters

Recommended first admin information architecture:

- `Dashboard`: market breadth, sync status, quick actions
- `Market`: stock search, daily bars, dragon tiger list, limit-up board, news
- `Analysis`: factor ranking, indicator views, screener results
- `Backtest`: strategy list, run history, result charts
- `Bot Ops`: bot status, command metrics, conversation audit
- `System`: data source health, sync logs, jobs, settings

### 3.4 Data and Storage

Keep PostgreSQL + TimescaleDB as the primary store.

Recommended storage roles:

- `PostgreSQL/TimescaleDB`: canonical transactional and time-series data
- `Redis`: cache, Celery broker/result backend, ephemeral bot session/rate-limit state
- local file/object storage later if needed for exported reports or uploaded research assets

Recommended early hypertables:

- `daily_bars`
- future `intraday_bars` if real-time or minute data is introduced

Recommended early non-time-series tables:

- `stocks`
- `dragon_tiger_lists`
- `limit_up_boards`
- `daily_news`
- `sync_jobs` or `sync_runs`
- `bot_events` or `bot_command_logs`

## 4. Mainstream Technology Decisions

The current stack is already close to the right mainstream choices for this scope.

### 4.1 Backend

- `FastAPI`: keep
- `SQLAlchemy 2.0 async`: keep
- `Alembic`: keep; every schema change must ship with migration
- `Celery + Redis`: keep for scheduled and deferred analysis workloads
- `Pydantic v2`: keep for contracts

### 4.2 Frontend

- `Next.js 15 App Router`: keep
- `React 18`: keep
- `Shadcn UI + Tailwind v4`: keep
- `TanStack Query`: keep
- `Zustand`: keep only for UI/local state, not server data duplication

### 4.3 Charts

The repo's stated chart policy is sensible and should stay:

- `Recharts`: KPI, trend, dashboard widgets
- `ECharts`: heatmaps, scatter plots, dense analytical visualizations
- `TradingView Lightweight Charts`: K-line/candlestick, price overlays, volume panes

### 4.4 Bot

- `lark-oapi` WebSocket mode: keep for first phase
- `Adapter pattern`: keep and enforce
- message cards + loading/update flow: keep, but move heavy work to async tasks as features deepen

### 4.5 Local Infra

- `Docker Compose` on `OrbStack`: keep as the default local stack
- default service ports remain `5000`, `5001`, `5432`, `6379`
- `8081` stays forbidden

## 5. Engineering Discipline ("Harness")

The project's engineering discipline is documented in `docs/engineering-harness.md`. That file is the authoritative checklist for contracts, migrations, dependencies, observability, testing, bot adapter rules, and Definition of Done. Read it before opening a PR.

Key rules at a glance:

- Public dependencies only (PyPI / npmjs.org / Docker Hub / GHCR)
- Every schema change ships with an Alembic migration
- Every route has Pydantic request/response schemas
- All errors use the shared envelope (`app/shared/errors.py`)
- Bot SDK imports stay inside `bot/adapters/<platform>/`
- Port 8081 is forbidden everywhere

## 6. Delivery Roadmap

### Phase 0: Foundation Alignment

Goal: make the skeleton internally consistent.

Deliverables:

- unify backend API contracts and frontend hooks
- add missing migrations for current models
- add base exception response format and global handlers
- add initial sync/job tracking table
- ensure local dev with OrbStack is one-command reliable
- add lint/test scripts that work end to end

Exit criteria:

- backend boots cleanly
- admin boots cleanly
- one data sync path succeeds locally
- frontend can read at least one real backend dataset

### Phase 1: Market Data MVP

Goal: create a useful A-share market data platform core.

Deliverables:

- stock master sync
- daily bars query and visualization
- dragon tiger list query and visualization
- limit-up board query and visualization
- daily news query and visualization
- sync status dashboard
- Feishu commands for `/help`, `/stock`, `/lhb`, `/zt`, `/news`

Exit criteria:

- admin and Feishu both expose the same core datasets
- scheduled sync jobs run via Celery
- failures and fallbacks are visible in logs

### Phase 2: Analysis MVP

Goal: turn data into decisions.

Deliverables:

- indicator library: MA, EMA, MACD, RSI, volume-related metrics
- stock screener APIs
- ranking/scoring endpoints
- admin analysis pages and chart overlays
- bot commands for common quick analysis

Exit criteria:

- users can screen stocks and inspect analysis results from both admin and bot

### Phase 3: Backtest and Strategy Operations

Goal: enable repeatable strategy validation.

Deliverables:

- strategy definition model
- parameterized backtest runs
- result persistence
- performance charts and trade summaries
- async run queue via Celery

### Phase 4: Governance and Multi-Platform Expansion

Goal: make the system operable and extensible.

Deliverables:

- auth and role-based access
- admin audit views
- bot rate limits and permission policy
- second bot adapter if desired

## 7. Recommended First Build Slice

The first slice should be intentionally narrow and valuable.

### Build this first

1. `Market data contract alignment`
   Align backend endpoints and frontend hooks around a single API shape for:
   - stock list
   - stock daily bars
   - stock quote
   - dragon tiger list
   - limit-up board
   - news

2. `Admin market dashboard`
   Replace placeholder cards with real queries for:
   - sync summary
   - top active stocks or latest synced stocks
   - latest dragon tiger list
   - latest limit-up board
   - latest news

3. `Feishu bot MVP`
   Keep `/help`, `/stock`, `/lhb`, `/zt`, `/news`, but ensure they all call stable services and return consistent structured responses.

4. `Job visibility`
   Add sync run records so the admin can show job history, last success time, record counts, and failures.

### Do not build first

- full auth system
- real trading or broker integration
- complex portfolio accounting
- high-frequency/intraday pipelines
- multi-bot support before Feishu is stable

## 8. Immediate Repository Priorities

Based on the current codebase, the next engineering priorities should be:

1. Resolve API contract mismatch between frontend hooks and backend routes.
2. Add real Alembic revisions for current models.
3. Introduce a standard API response/error envelope.
4. Add admin pages for real market data instead of placeholders.
5. Add tests for `market_data` services and routers.
6. Add persistence/visibility for sync runs and bot command logs.
7. Move any potentially heavy bot analysis flow to Celery-backed async updates.

## 9. Definition of Done for New Features

A feature is only done when it includes all of the following:

- code implementation
- migration if schema changed
- tests
- logging/visibility
- docs update if workflow or architecture changed
- admin and/or bot integration if the feature is user-facing

## 10. Suggested Team Rhythm

Use a small but repeatable cadence:

1. write or adjust the contract
2. implement backend service
3. expose HTTP endpoint
4. wire admin view and/or bot command
5. add tests and docs
6. verify in local OrbStack environment

If a more specific Harness standard exists internally, this document should be updated to match it rather than letting local conventions drift.
