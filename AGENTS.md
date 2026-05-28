# Project: A 股量化分析系统 (trade_bot)

## Overview

A 股量化分析系统，支持管理后台、量化分析引擎、通用 Bot 接口（首期接入飞书）。前后端分离 + Bot 多端接入架构。

## Tech Stack

- **Backend**: FastAPI (Python 3.12+), SQLAlchemy 2.0, Alembic, Celery, Redis
- **Database**: TimescaleDB (PostgreSQL extension)
- **Data Sources**: Tushare Pro + AKShare (DataFacade 主备降级)
- **Frontend**: React 18 + Next.js 15 (App Router), Shadcn UI + Tailwind v4, ECharts + Recharts + LWC, Turborepo + pnpm
- **Bot**: lark-oapi SDK (WebSocket mode), Adapter pattern
- **Infra**: Docker Compose (OrbStack)

## Project Structure

```
trade_bot/
├── backend/          # Python 后端 (FastAPI)
├── frontend/         # 前端 (Turborepo monorepo)
├── docker-compose.yml
├── AGENTS.md
├── Makefile
└── .env.example
```

## Port Allocation

- Backend (FastAPI): 5000
- Frontend (Next.js): 5001
- TimescaleDB: 5432
- Redis: 6379

**NEVER use port 8081** — it is reserved for other critical services on both local and server environments. This applies to all services, Docker containers, dev servers, and any tooling.

## Development Commands

- `make dev` — 启动全部服务 (Docker Compose)
- `make dev-backend` — 仅启动后端依赖 (DB + Redis) 并运行 FastAPI dev server
- `make dev-frontend` — 启动前端 dev server
- `make migrate` — 运行数据库迁移
- `make test` — 运行测试套件
- `make sync-data` — 手动触发行情数据同步

## Backend Conventions

- **Dependency management**: uv (pyproject.toml)
- **Python version**: 3.12+
- **Code style**: ruff (lint + format), isort
- **Type hints**: 必须使用 type hints，pydantic v2 做验证
- **Async**: 所有 I/O 操作必须用 async，SQLAlchemy 用 async engine
- **Module structure**: feature-based modules under `app/modules/`
- **API versioning**: `/api/v1/` prefix
- **Error handling**: 统一 exception handler，返回标准错误格式

## Frontend Conventions

- **Package manager**: pnpm
- **Build**: Turborepo
- **Code style**: ESLint + Prettier
- **TypeScript**: strict mode
- **Components**: Shadcn UI (new-york style, zinc base), 共享封装放 packages/ui
- **Charts**: 三层图表策略 - Recharts (Shadcn Chart, KPI/折线), ECharts (热力图/散点图), TradingView LWC (K线/实时)
- **State**: Zustand (UI) + TanStack Query (server)
- **CSS**: Tailwind v4 CSS-first 配置 (无 tailwind.config.ts), oklch 色彩空间
- **A-share 配色**: 红涨绿跌 (text-stock-up = red, text-stock-down = green)
- **Dark mode**: next-themes (class strategy)

## Bot Conventions

- **Adapter pattern**: 所有 Bot 平台实现 BotAdapter ABC
- **Feishu**: lark-oapi SDK WebSocket 模式 (免公网 IP)
- **Commands**: `/command args` 格式，命令处理器放 `commands/`
- **Async results**: 卡片原地更新模式 (loading → result)
- **Middleware**: Auth → RateLimit → Logging pipeline

## Database Conventions

- **Migrations**: Alembic, 每次模型变更必须生成迁移
- **Time-series data**: 使用 TimescaleDB hypertable (daily_bars 等)
- **Connection**: async SQLAlchemy engine + async session

## Testing Conventions

- **Backend**: pytest + pytest-asyncio
- **Frontend**: Vitest + Playwright
- **Test structure**: mirrors source structure under `tests/`

## Environment Variables

Copy `.env.example` to `.env` and fill in values. Required:
- `DATABASE_URL`: TimescaleDB connection string
- `REDIS_URL`: Redis connection string
- `TUSHARE_TOKEN`: Tushare Pro API token
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET`: 飞书 Bot credentials
