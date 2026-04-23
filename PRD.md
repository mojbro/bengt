# Personal AI Assistant – Product Requirements Document

**Version:** 0.1 (MVP)
**Status:** Draft
**Last updated:** 2026-04-23

---

## 1. Summary

A self-hosted personal AI assistant designed to function as a "second brain" for a busy CTO. The assistant is accessed via a web app (responsive, usable on desktop and mobile), has persistent memory through a local markdown vault, and can schedule its own future actions.

The MVP focuses on the pure core of the product: a conversational assistant with persistent memory, editable notes, and self-scheduling capability. External integrations (email, calendar, SharePoint) are explicitly out of scope for v0.1 and will be added incrementally in later versions.

## 2. Goals and non-goals

### Goals for v0.1
- Daily-usable personal assistant within 2–3 weeks of build time
- A conversational interface that remembers context across sessions
- A markdown-based vault that is the single source of truth for notes, todos, memory, and preferences – editable by both the user and the agent
- Self-scheduling: the agent can set up future actions it will take (reminders, recurring tasks, conditional checks)
- Local-first: everything runs in Docker, data stays on the user's machine
- A pluggable LLM backend starting with a single API-key-based provider

### Non-goals for v0.1
- Email, calendar, SharePoint, or any external data source integration
- Multi-user support
- GDPR-compliant hosting for professional personal data (the MVP is built for personal use with non-sensitive data only)
- Mobile push notifications when the app is closed
- Voice input
- Local LLM execution
- Internationalization (English-only UI, though the user may converse with the agent in any language the LLM supports)

### Goals for future versions (out of v0.1 scope)
See §13 for the full backlog.

## 3. Users

A single user: the product owner. A CTO who is:
- Disorganized by self-description
- Overwhelmed by email, meetings, commitments, and documents
- Comfortable with technical tools, Docker, and self-hosting
- Works primarily in English professionally, Swedish natively

Multi-user support is an explicit non-goal for v0.1 but the architecture should not preclude it.

## 4. Core concepts

### 4.1 The vault
A Git-versioned directory of markdown files that serves as the user's "second brain". Structure:

```
vault/
├── notes/           # free-form notes, meeting minutes, ideas
├── todos.md         # Obsidian Tasks-compatible todo list
├── memory.md        # long-term facts the agent has learned
├── preferences.md   # user preferences the agent has learned
└── .git/            # automatic version history
```

Both the user (via the web app) and the agent (via tools) can read and write any file in the vault. Every change is auto-committed to Git.

The vault format is intentionally compatible with Obsidian so the user can open the same directory in Obsidian on desktop without friction.

### 4.2 Todo format
Todos live in `todos.md` using GitHub Flavored Markdown + Obsidian Tasks conventions:

```markdown
- [ ] Call Volvo about contract 📅 2026-04-25 🔼 #work @erik
- [x] Send invoice ✅ 2026-04-22
```

Legend:
- `📅 YYYY-MM-DD` = due date
- `🔼 / ⏫ / 🔽` = priority (high / highest / low)
- `#tag` = categorization
- `@name` = person reference
- `✅ YYYY-MM-DD` = completion date

### 4.3 Agent tools
The LLM can invoke a fixed, small set of tools. No shell, no code execution, no network access beyond these tools.

- `search_vault(query)` – semantic search across the vault via ChromaDB
- `list_vault(path?)` – directory listing
- `read_file(path)` – read a markdown file
- `write_file(path, content)` – create or fully overwrite a file
- `edit_file(path, old_string, new_string)` – targeted edit; preferred over `write_file` for large files to save tokens and reduce the risk of regenerated-file corruption
- `append_to_file(path, content)` – append to end of file
- `schedule_job(when, instruction)` – schedule a future agent invocation
- `list_scheduled_jobs()` – enumerate pending jobs
- `cancel_job(id)` – cancel a scheduled job

### 4.4 Scheduled jobs
The agent can schedule future invocations of itself. A scheduled job consists of:
- A trigger (absolute timestamp or cron expression for recurring)
- A natural-language instruction ("Remind the user to prepare for the board meeting")
- Optional context references (file paths in the vault)

When the trigger fires, the scheduler invokes the agent with the instruction as a user message. The agent then decides what to do – typically send a chat message to the user or write to the vault.

This mechanism allows the user to construct custom routines directly in conversation:
- "Every Monday at 08:00, ask me what I want to focus on this week"
- "In three days, check whether I've written anything about the board meeting, and remind me if not"
- "Tomorrow at 14:00, remind me to call my father"

### 4.5 Memory model
Three distinct memory layers:

1. **Short-term**: recent messages in the current chat thread, included in the LLM context window directly.
2. **Long-term (structured)**: `memory.md` and `preferences.md` are always included in the agent's system context. The agent writes to these files as it learns about the user.
3. **Long-term (searchable)**: the full vault is indexed in ChromaDB. The agent uses `search_vault` when it needs to recall something not present in short-term or structured memory.

## 5. User interface

### 5.1 Stack
- Vite + React 18 + TypeScript
- TanStack Query for server state
- React Router (or TanStack Router) for routing
- shadcn/ui + Tailwind for components and styling
- Native WebSocket API for streaming chat and real-time notifications
- `@uiw/react-md-editor` (or equivalent) for the markdown editor

### 5.2 Layout – desktop
A two-pane layout:

- **Left sidebar**: vault file tree, plus links to Chat and Scheduled Jobs views
- **Main pane**: either the chat view, a markdown editor for the selected file, or the scheduled jobs list

### 5.3 Layout – mobile
A tabbed layout with three tabs at the bottom:
- Chat (default)
- Vault (file tree → editor)
- Scheduled

### 5.4 Chat view
- Standard chat UI: message list, input at bottom
- Streaming responses from the LLM via WebSocket
- **Multiple conversation threads** that the user can switch between; history persists across sessions. All past threads are retained — a future tool (`search_conversations`) will let the agent search across them.
- The agent can render tool invocations inline ("*Searching vault for 'Volvo'...*") for transparency
- Support for multi-turn tool use (the agent may call several tools before replying)

### 5.5 Editor view
- Simple textarea with monospace font for MVP
- Live preview as a stretch goal for v0.1
- Autosave after N seconds of inactivity (default 3)
- Conflict handling: if the file has been modified on disk since the user started editing (e.g. by the agent), show a reload prompt

### 5.6 Scheduled jobs view
- List of pending jobs with their triggers, instructions, and next-fire times
- Ability to cancel a job
- No in-UI creation for MVP; jobs are created via conversation with the agent

### 5.7 Notifications
When a scheduled job fires while the web app is open, the resulting agent message appears in the chat and a visual indicator is shown (e.g. badge on the Chat tab). Push notifications when the app is closed are out of scope for v0.1.

## 6. Backend

### 6.1 Stack
- Python 3.12+
- FastAPI
- SQLAlchemy + SQLite
- APScheduler with SQLAlchemy job store
- ChromaDB (local, embedded mode)
- GitPython for vault version control
- `websockets` or FastAPI's native WebSocket support

### 6.2 Data model (SQLite)
- `conversations` – chat threads
- `messages` – individual messages (user, assistant, tool_call, tool_result)
- `scheduled_jobs` – APScheduler jobs with their natural-language instructions and context references
- `audit_log` – every LLM call and tool invocation, with inputs, outputs, tokens, and cost
- `daily_budget` – running cost tracking per day

### 6.3 LLM abstraction
A thin interface with pluggable providers. For MVP: one provider (user's choice of OpenAI, Anthropic, or DeepSeek – configured via env var). The interface must support:
- Streaming responses
- Tool/function calling
- Token counting
- Cost estimation

### 6.4 Agent loop
A ReAct-style loop:
1. Build context: system prompt + `memory.md` + `preferences.md` + recent messages + current user message
2. Call LLM with tools available
3. If LLM returns tool calls, execute them and feed results back
4. Loop until LLM returns a final text response
5. Stream response to user, persist to `messages` table

### 6.5 Scheduler
APScheduler runs in-process. When a job fires:
1. Load the natural-language instruction and any context references
2. Invoke the agent with the instruction as a user message
3. The resulting agent response is pushed to the user's active WebSocket connection(s) and persisted to the relevant conversation

### 6.6 Vault operations
All reads and writes to the vault go through a VaultService that:
- Enforces path safety (no escaping the vault directory)
- Updates the ChromaDB index after writes
- Auto-commits changes to Git with a meaningful message (`agent: updated todos.md` / `user: edited notes/meeting-with-anna.md`)

### 6.7 Cost control
A hard daily budget (default $5) is enforced. When exceeded, the LLM abstraction refuses further calls for the remainder of the day and the agent responds with an error message.

## 7. Authentication and security

### 7.1 Auth
Single-user, password-based authentication with server-issued session cookies. HTTPS is required for any deployment outside localhost.

TOTP and other hardening is deferred to v0.2.

### 7.2 Secrets
LLM API keys are stored in `.env` for MVP. Encrypted-at-rest storage in SQLite is deferred to v0.2.

### 7.3 Audit log
Every LLM call and every tool invocation is logged. The log is viewable in the app (simple table) for debugging and trust-building.

## 8. Deployment

### 8.1 Docker Compose
A single `docker-compose.yml` that runs:
- `backend` – FastAPI + agent + scheduler
- `frontend` – static Vite build served via a minimal web server (or served by FastAPI directly)

Volumes:
- `${VAULT_HOST_PATH}` → `/app/vault` – the markdown vault, mounted read-write. Host path is user-configurable and should live outside this repo for portability; falls back to `./vault` if unset.
- `./data` – SQLite, ChromaDB persistence

### 8.2 Configuration
All runtime config via environment variables:
- `LLM_PROVIDER` (openai / anthropic / deepseek)
- `LLM_API_KEY`
- `LLM_MODEL`
- `DAILY_BUDGET_USD`
- `AUTH_PASSWORD` (hashed at startup)
- `VAULT_PATH`
- `INBOX_SCAN_INTERVAL_MINUTES` (unused in v0.1 but reserved)

## 9. Non-functional requirements

- **Latency**: chat response start (first token) under 2 seconds for typical queries
- **Reliability**: scheduled jobs fire within 30 seconds of their trigger time, even if the user is offline (as long as the container is running)
- **Observability**: audit log is comprehensive enough to reconstruct any agent decision
- **Portability**: the entire system must be runnable with a single `docker compose up`

## 10. Success criteria for MVP

The MVP is considered successful if:
1. The user uses it daily for at least two weeks without significant friction
2. The agent demonstrates useful memory (answers "what did I say about X?" questions correctly using the vault)
3. At least five self-scheduled jobs are created and fire correctly during the validation period
4. The vault can be edited interchangeably via the web app and Obsidian without data loss

## 11. Build plan (suggested)

A proposed sequence for Claude Code:

1. Project scaffold (Docker Compose, FastAPI skeleton, Vite skeleton)
2. Vault service (read/write/list, Git auto-commit, path safety)
3. ChromaDB indexer (index vault on startup, reindex on writes)
4. LLM abstraction + one provider implementation
5. Agent loop with tool calling (mock tools first)
6. Real tool implementations (vault tools, scheduling tools)
7. Conversation persistence and retrieval
8. REST API surface (auth, vault CRUD, conversations)
9. WebSocket for streaming chat
10. Frontend: auth, routing, layout
11. Frontend: chat view with streaming
12. Frontend: vault file tree + editor
13. Frontend: scheduled jobs view
14. APScheduler integration and job firing flow
15. Audit log + cost tracking + daily budget enforcement
16. Polish: responsive mobile layout, error handling, loading states

## 12. Open questions (to resolve during or after MVP)

- How the agent decides *when* to write to `memory.md` vs. `preferences.md` vs. a note in `notes/` – this will require prompt-engineering iteration
- Whether the agent should proactively summarize recent notes/conversations into `memory.md` on a schedule, or only when it perceives a need
- Markdown editor: textarea only, or a richer editor like CodeMirror/Monaco?

## 13. Post-MVP backlog

Features deliberately excluded from v0.1, to be prioritized later:

### v0.2 candidates
- Telegram interface in parallel with web app
- Encrypted-at-rest API key storage
- Email integration via Microsoft Graph API (read, archive, draft – never send or delete)
- Approval queue for destructive actions
- PWA support with web push notifications
- Web search tool for the agent

### v0.3+ candidates
- Calendar integration (work calendar full access, personal calendar read-only)
- SharePoint read-only integration
- Data warehouse read-only integration
- Local LLM support (Ollama) for GDPR-sensitive use
- Historical mail ingestion and RAG
- Multi-user support with per-user vaults
- Internationalization (Swedish UI)
- TOTP / hardened auth
- Voice input via Whisper
- Shared company-wide knowledge vault separate from personal vaults
- Spaces concept for separating contexts (work/personal)

## 14. Architectural principles (to preserve)

These principles should not be violated as the product grows:

1. **The LLM never has direct access to external APIs.** It always goes through Python-executed tools with validated inputs and outputs.
2. **The vault is plain markdown on disk.** No proprietary format, no database-locked content. The user owns the data.
3. **Every destructive action either has an undo (via Git) or requires user approval.**
4. **Every agent decision is auditable.** The audit log is a first-class feature.
5. **Pluggability over lock-in.** LLM providers, storage backends, and interfaces should be swappable.
6. **Local-first.** The system must be runnable entirely on the user's own hardware.

---

*End of PRD v0.1*
