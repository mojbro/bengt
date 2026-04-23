# bengt

Self-hosted personal AI assistant — a "second brain." See `PRD.md` for the full product spec (v0.1). `bengt` is the tentative name; keep it out of code and confined to a few user-facing strings.

## Stack

- **Backend**: Python 3.12 managed by [uv](https://docs.astral.sh/uv/) + FastAPI + SQLite + APScheduler + ChromaDB + GitPython (see PRD §6.1). Dependencies are pinned in `backend/uv.lock`; the Docker image does `uv sync --frozen`.
- **Frontend**: Vite + React 18 + TypeScript + shadcn/ui + Tailwind (see PRD §5.1)
- **LLM**: pluggable; OpenAI first for MVP. The abstraction must stay provider-agnostic — Ollama comes next.
- **Deployment**: Docker Compose, local-first

## Layout

```
backend/    FastAPI app, agent loop, scheduler, vault service
frontend/   Vite + React app
data/       SQLite + ChromaDB persistence (gitignored)
PRD.md      product spec — source of truth for scope and decisions
```

The **vault** lives on the host at `VAULT_HOST_PATH` (from `.env`) — typically outside this repo (e.g. `$HOME/bengt-vault`), so notes stay portable and Obsidian-friendly. Docker bind-mounts it into the backend container at `VAULT_PATH` (`/app/vault`). It's git-versioned in place by the VaultService on every write. If `VAULT_HOST_PATH` is unset, compose falls back to `./vault` inside the repo (gitignored) — fine for quick experiments.

## Running

```sh
cp .env.example .env       # then fill in LLM_API_KEY etc.
docker compose up --build
```

- Frontend: http://localhost:3500 (dev mode, HMR, proxies `/api/*` → backend)
- Backend:  http://localhost:3501 (FastAPI; `GET /api/health` for liveness)

## Build progress (PRD §11)

- [x] 1. Project scaffold (Docker Compose, FastAPI skeleton, Vite skeleton)
- [x] 2. Vault service (read/write/list, Git auto-commit, path safety)
- [x] 3. ChromaDB indexer
- [x] 4. LLM abstraction + one provider (OpenAI)
- [x] 5. Agent loop with tool calling (mock tools first)
- [x] 6. Real tool implementations (vault tools, scheduling tools)
- [x] 7. Conversation persistence and retrieval (multiple threads)
- [x] 8. REST API surface (auth, vault CRUD, conversations)
- [x] 9. WebSocket for streaming chat
- [x] 10. Frontend: auth, routing, layout
- [x] 11. Frontend: chat view with streaming
- [x] 12. Frontend: vault file tree + editor
- [x] 13. Frontend: scheduled jobs view
- [x] 14. APScheduler integration and job firing flow
- [x] 15. Audit log + cost tracking + daily budget enforcement
- [x] 16. Polish: responsive mobile layout, error handling, loading states

## Non-negotiable architectural rails (PRD §14)

1. LLM never touches external APIs directly — only Python-executed tools with validated inputs/outputs.
2. Vault is plain markdown on disk. No proprietary formats.
3. Every destructive action either has an undo (via the vault's git history) or requires explicit user approval.
4. Every agent decision is auditable — the audit log is a first-class feature.
5. Pluggability over lock-in for LLM providers, storage, and interfaces.
6. Local-first — must run entirely on the user's own hardware.

Violate these only with explicit user sign-off in the conversation.

## Conventions

- The product name `bengt` appears in a handful of user-facing strings only (HTML title, top heading, FastAPI app title, this file, PRD). Don't bake it into package names, service names, DB names, URL paths, class names, or env vars — use generic terms ("backend", "frontend", "agent").
- Two directories — `vault/` and `data/` — are runtime state and gitignored. Docker creates them on first `up`.
- Backend Python deps: add to `backend/pyproject.toml`, then regenerate the lock with `docker run --rm -v "$PWD/backend:/work" -w /work ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv lock` (or `uv lock` locally if you have uv installed). Commit both `pyproject.toml` and `uv.lock`.
- Run backend tests with `docker compose exec backend pytest -q` (151 tests). Integration tests (5, opt-in) hit real external services (OpenAI + the public web): `docker compose exec backend pytest -m integration -v`.
- Web tools live in `app/agent/web_tools.py`: `web_search` (DuckDuckGo via `duckduckgo-search`, no API key) and `fetch_url` (reader-mode extraction via `trafilatura`). Both run their blocking I/O in `asyncio.to_thread`. `fetch_url` output is truncated at 8000 chars; errors become the tool result so the agent can recover rather than crashing the turn.
- Vault write conflict detection: `GET /api/vault/file` returns `modified_at`; `PUT /api/vault/file` accepts optional `expected_modified_at` and returns **409** if the on-disk mtime is newer (0.5s epsilon for filesystem precision). The Editor tracks mtime, sends it on save, and on 409 shows a banner with **Reload (discard my edits)** and **Force save** (which sends no expected mtime). Prevents the agent silently overwriting user edits and vice-versa.
- Audit + budget: every LLM call + tool invocation writes to `audit_log` (timestamp, kind, cost_usd, JSON `data`). `BudgetService` aggregates `cost_usd` for the current UTC day against `DAILY_BUDGET_USD`; `AgentLoop` checks `budget.exceeded()` before each iteration and emits `AgentError` if spent. Truncation keeps the log compact — tool arguments over 200 chars are truncated in the stored blob, result previews capped at 400. The frontend `/audit` page polls `/api/audit/recent` + `/api/audit/budget` every 10s.
- Scheduled job firing: `app/scheduler_runner.py` holds a module-level service registry (services can't be pickled through APScheduler kwargs). `fire_scheduled_job(instruction)` is the callable added to every scheduled job — runs the agent, persists the turn to a dedicated "Scheduled" conversation (ID pinned in `data/.scheduled_conversation_id`), and broadcasts a `notification` event to all active chat WebSockets via `app.state.ws_manager`. Lifespan starts/stops the scheduler; `Settings.scheduler_autostart=False` in tests keeps jobs inert. Frontend `useChatStream` handles the notification by invalidating the conversations list and the affected thread.
- `/api/scheduler/jobs` (GET list, DELETE cancel) is the HTTP surface over the APScheduler instance — separate from the agent-facing `schedule_job` / `list_scheduled_jobs` / `cancel_job` tools. Both manipulate the same store (`app.state.scheduler`), so what the user cancels in the UI disappears from the agent's view too.
- Streaming chat at `ws://.../api/chat/ws`. Client sends `{conversation_id, content}`, server streams `{type: text|tool_start|tool_result|usage|done|error}`. Session cookie gates the handshake (close 1008 if unauthed). `AgentLoop` now emits an internal `AgentTurnEnd(text, tool_calls)` after each LLM iteration so `chat.py` has a single persistence boundary — every agent turn and tool result lands in the `messages` table as it streams.
- Frontend: React Router 6 + Tailwind + TanStack Query. `App.tsx` wires the router; `ProtectedRoute` guards on `GET /api/auth/me`; `AppShell` is a sidebar (conversation list, `+ New`) + main `<Outlet />`. API client at `src/api/client.ts` (`apiFetch`, `ApiError`) always sends `credentials: 'include'` so session cookies flow through the Vite dev-server proxy.
- Chat view (`src/components/ChatView.tsx`): DB-backed message history via `useConversation(id)`, live streaming via `useChatStream(id)` over the `/api/chat/ws` WebSocket (Vite proxies with `ws: true`). Optimistic user bubble lands in the query cache on send; a `done` event from the server invalidates the query to replace with real DB rows. Tool invocations render inline as small monospace boxes with live "pending" indicators while the tool is running.
- REST API is mounted under `/api/*`. `app/api/` has router modules: `auth` (login/logout/me with starlette SessionMiddleware; session secret persisted at `data/.session_secret`), `vault` (tree/file — all gated by `require_auth`), `conversations` (CRUD — also auth-gated). Services are exposed as deps from `app.api.deps`. Streaming chat lands in step 9.
- `app.main.create_app(settings)` is the app factory — use it in tests with a `Settings` pointed at tmp paths and drive with `fastapi.testclient.TestClient` (which runs lifespan).
- Conversation persistence: `app/db/` has SQLAlchemy 2.x models (`Conversation`, `Message`) and `ConversationService` at `app.state.conversations`. SQLite lives at `/app/data/app.db` (bind-mounted → `./data/app.db` on host). `ConversationService.to_llm_messages(conv_id)` converts DB rows to `llm.Message` for feeding `AgentLoop.run(history=...)`. AgentLoop stays pure; the caller (step 8/9) owns the persist-as-you-stream flow.
- Real agent tools live in `app/agent/vault_tools.py` (search/list/read/write/edit/append — all writes commit as `actor="agent"`) and `app/agent/scheduler_tools.py` (schedule/list/cancel). The APScheduler instance is created but intentionally NOT started in step 6; jobs are stored and listable via triggers, but won't fire until step 14 swaps `job_fire_placeholder` for real agent invocation and starts the scheduler. `schedule_job`'s `when` auto-detects ISO 8601 datetime vs 5-field cron; naive datetimes are assumed UTC.
- The agent loop (`app/agent/`) is ReAct-style: system prompt → LLM stream → collect tool calls → execute → feed back → repeat until text-only or `max_iterations`. It emits agent-level events (`AgentText | AgentToolStart | AgentToolResult | AgentUsage | AgentError | AgentDone`) — not to be confused with raw LLM stream events. Tools live in `app.state.tools` (a `ToolRegistry`); swap `register_mock_tools` for real ones in step 6.
- The LLM layer (`app/llm/`) is provider-agnostic by design. `LLMProvider` is a Protocol; `OpenAIProvider` is the current impl; Ollama slots in without touching call sites. All wire-format translation stays inside each provider's file — nothing OpenAI-specific leaks through the Protocol. Adding a new provider: add a class with `.name`, `.model`, `.stream(...)`, and a branch in `factory.build_provider`. Add its pricing to `app/llm/pricing.py` when known.
- Semantic search uses ChromaDB's default (local, ONNX-based) embeddings — no cloud calls for search. The model downloads on first use and caches in the container; persists as long as the container isn't recreated. Chroma data lives at `data/chroma/` (gitignored).
