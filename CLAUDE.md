# bengt

Self-hosted personal AI assistant — a "second brain." See `PRD.md` for the full product spec (v0.1). `bengt` is the tentative name; keep it out of code and confined to a few user-facing strings.

## Stack

- **Backend**: Python 3.12 + FastAPI + SQLite + APScheduler + ChromaDB + GitPython (see PRD §6.1)
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
- [ ] 2. Vault service (read/write/list, Git auto-commit, path safety)
- [ ] 3. ChromaDB indexer
- [ ] 4. LLM abstraction + one provider (OpenAI)
- [ ] 5. Agent loop with tool calling (mock tools first)
- [ ] 6. Real tool implementations (vault tools, scheduling tools)
- [ ] 7. Conversation persistence and retrieval (multiple threads)
- [ ] 8. REST API surface (auth, vault CRUD, conversations)
- [ ] 9. WebSocket for streaming chat
- [ ] 10. Frontend: auth, routing, layout
- [ ] 11. Frontend: chat view with streaming
- [ ] 12. Frontend: vault file tree + editor
- [ ] 13. Frontend: scheduled jobs view
- [ ] 14. APScheduler integration and job firing flow
- [ ] 15. Audit log + cost tracking + daily budget enforcement
- [ ] 16. Polish: responsive mobile layout, error handling, loading states

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
