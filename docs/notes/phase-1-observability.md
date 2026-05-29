# Phase 1 沉淀：可观测性基线（sync_runs + bot_command_logs）

**Status**: shipped (2026-05-29)
**Scope**: backend observability, Celery beat, admin /system page

## 为什么要做

第 0 阶段我们补齐了错误格式、request id、结构化日志、TimescaleDB hypertable，
但所有「跑了什么、跑成功没、跑了多久」这件事仍然只活在 loguru 输出里——
没法做事后审计，admin 页面也看不到任何运行轨迹。Phase 1 的目标是把这两条
关键的写入流水线（行情同步、Bot 命令）落到表里，前端有一个最小可见的视图。

## 设计决策

### 1. tracking 在 service 层，不在 task 层

```python
async def sync_dragon_tiger_list(self, trade_date):
    if await self.repo.has_dragon_tiger_data(trade_date):
        await self.sync_runs.mark_skipped("dragon_tiger", target=str(trade_date), reason="data already present")
        return SyncResult(synced=0, ...)
    async with self.sync_runs.track("dragon_tiger", target=str(trade_date)) as handle:
        ...
        handle.synced_count = count
```

**Why**：HTTP 触发的手动重跑、Celery beat 触发的定时跑，走的是同一个 service
方法。把 tracking 放在 service 层，两条入口都被覆盖；放在 Celery task 层
就漏掉手动重跑。

**副作用**：service 现在与 `sync_runs` 模块耦合，但这是合理的——这个项目的
service 层本来就负责「业务编排 + 副作用」，可观测性也是副作用之一。

### 2. skip 不进 track() 上下文

`mark_skipped` 是独立 API，不是 `track()` 里的一个分支。

**Why**：`track()` 是一个上下文管理器，进入即建一行 sync_runs，退出时
mark_success/mark_failed。如果跳过也走 `track()`，就需要在 yield 之前/之后
判断，handle 上还要加 `skip_reason` 字段——把简单事情搞复杂。
独立 `mark_skipped` 一行 create + 一行 mark，含义直白，调用点也清楚。

### 3. RunHandle.synced_count 在 yield 之后读

```python
@asynccontextmanager
async def track(...):
    run = await self.repo.create(...)
    handle = RunHandle(run_id=run.id)
    try:
        yield handle
    except Exception as exc:
        await self.repo.mark_failed(run.id, error=str(exc)[:1000])
        raise
    else:
        await self.repo.mark_success(run.id, synced_count=handle.synced_count, ...)
```

**Why**：调用方在 `async with` 内部赋值 `handle.synced_count = count`，
service 在 `else` 分支读出来。没有用全局变量，没有用 contextvar，
没有让调用方传 callback——dataclass + 引用语义就够了。

错误信息硬截断到 1000 字符（与 BotCommandLog.error 字段一致）。Tushare/AKShare
的异常 traceback 偶尔很长，截断保护表结构和日志可读性。

### 4. Bot 命令日志：在 dispatch 站点埋点

```python
async def _dispatch_command(self, message):
    handler, args = self.router.get_handler(message.text)
    platform = next(iter(self.adapters.keys()), "unknown")
    if handler is None:
        await self._reply_text(...)
        await self._record_command_log(command="<no_command>", args_text=message.text, ...)
        return
    started = time.monotonic()
    try:
        result = await handler.handle(message, args)
    except Exception as exc:
        await self._record_command_log(..., error=str(exc)[:1000])
        raise
    ...
    await self._record_command_log(..., error=None)
```

**关键不变量**：
- 未命中命令也记录一行 (`command="<no_command>"`)，方便观察用户在打什么乱七八糟的指令。
- 命令异常先记录、再 re-raise，调用栈不丢。
- `_record_command_log` 内部 `try/except` 吞 DB 异常——可观测性失败不能影响用户回复。

**platform 字段**：今天只有 Feishu 一个 adapter，但写成 `next(iter(self.adapters.keys()), "unknown")`，
将来加 DingTalk / Slack 时不需要再改 service。

## 表结构要点

### `sync_runs`

| 字段 | 类型 | 备注 |
|---|---|---|
| job_name | varchar(50) | 例：`stock_list`, `daily_bars`, `dragon_tiger`, `limit_up`, `news` |
| target | varchar(100) nullable | 例：`600519`、`2026-05-27`，标识本次跑的对象 |
| status | varchar(20) | `running` / `success` / `failed` / `skipped` |
| meta | jsonb nullable | 例：`{"days": 30}` |
| synced_count | int nullable | success 时填，skipped/failed 不填 |
| duration_ms | int nullable | success 时填 |
| error | varchar(1000) nullable | failed 时填 |
| created_at | datetime | 索引 |
| finished_at | datetime nullable | success/failed/skipped 时填 |

### `bot_command_logs`

| 字段 | 类型 | 备注 |
|---|---|---|
| platform | varchar(20) | `feishu`、未来扩展 |
| chat_id | varchar(100) | |
| user_id | varchar(100) nullable | |
| command | varchar(50) | `/stock` / `<no_command>` |
| args_text | varchar(500) nullable | hard-truncated 到 500 |
| status | varchar(20) | `success` / `failed` |
| error | varchar(1000) nullable | hard-truncated 到 1000 |
| duration_ms | int nullable | |
| created_at | datetime | 索引 |

## 测试覆盖

- `tests/unit/test_sync_run_service.py` — track 成功/失败/截断、mark_skipped 共 4 例
- `tests/unit/test_market_data_sync_tracking.py` — sync_dragon_tiger_list 的 happy/skip/empty 三条路径
- `tests/unit/test_bot_command_logging.py` — 成功/未知命令/异常/持久化失败吞异常 共 4 例
- `tests/unit/test_celery_tasks.py` — 5 个 beat 入口被正确调度

全套单测 30 例，`uv run pytest tests/ -q` 全绿。

## 后续延展

1. **Admin 检索/过滤**：`/system` 页面目前只列出最近 50 条。下一步加 status 过滤、job_name 过滤、target 模糊搜索。
2. **告警**：`sync_runs.status == 'failed'` 持续 N 次 → Feishu 群推送。
3. **TTL 清理**：bot_command_logs 写量随用户增长，beat 加一个 `cleanup_bot_command_logs` 周任务，保留 30 天。
4. **跨服务串联**：`request_id`（HTTP 中间件）尚未流入 sync_runs / bot_command_logs，等 Phase 2 接 trace 时统一处理。
