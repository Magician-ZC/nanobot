# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development commands

### Python environment (root project)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Core CLI / gateway
```bash
# Initial local setup (creates ~/.nanobot/config.json and workspace)
nanobot onboard

# Interactive CLI chat
nanobot agent

# One-shot prompt
nanobot agent -m "Hello"

# Start multi-channel gateway
nanobot gateway

# Check configured providers/channels/workspace
nanobot status
nanobot channels status

# Scheduled tasks
nanobot cron add --name "task" --message "msg" --cron "0 9 * * *"
nanobot cron list
nanobot cron remove <job_id>
```

### Lint and tests
```bash
# Lint
ruff check .

# Run all tests
pytest

# Run one test file
pytest tests/test_commands.py

# Run one test case
pytest tests/test_commands.py::test_some_case
```

### Control Plane (backend + frontend)
```bash
# Backend deps (from repo root)
pip install -e ./control_plane

# Run control plane API server
python control_plane/run.py

# Run control plane API on custom port
python control_plane/run.py --port 9090

# Frontend dev/build
cd control_plane/frontend
npm install
npm run dev
npm run build
```

### Docker
```bash
# Main gateway stack
docker compose up -d nanobot-gateway

# Control plane stack
docker compose -f control_plane/docker-compose.yml up -d
```

### WhatsApp bridge (TypeScript)
```bash
cd bridge
npm install
npm run build
npm run dev
```

## High-level architecture

### 1) Runtime flow: channel -> bus -> agent -> bus -> channel
- `nanobot/cli/commands.py` is the operational entrypoint for nearly all workflows (`nanobot agent`, `nanobot gateway`, `nanobot register`, provider OAuth login, cron commands).
- `nanobot/bus/queue.py` defines a simple async message bus with inbound/outbound queues to decouple channel I/O from reasoning.
- `nanobot/channels/manager.py` initializes enabled channels from config and dispatches outbound messages.
- `nanobot/agent/loop.py` is the core orchestrator: builds prompt context, calls LLM, executes tools, persists session state, and handles progress/tool-hint streaming.

### 2) Agent core
- `AgentLoop` in `nanobot/agent/loop.py` owns:
  - tool registry initialization (filesystem, shell, web, message, spawn, cron, MCP)
  - iterative LLM/tool-call loop with max-iteration guard
  - per-session routing and slash commands (`/new`, `/help`)
  - memory consolidation trigger logic
- `nanobot/agent/context.py` builds system prompt from:
  - identity/runtime block
  - workspace bootstrap docs (`AGENTS.md`, `SOUL.md`, etc.)
  - long-term memory (`memory/MEMORY.md`)
  - skills summary and always-loaded skills
- `nanobot/agent/tools/registry.py` centralizes tool schema exposure + execution + validation.

### 3) Conversation persistence and memory
- `nanobot/session/manager.py` stores each session as JSONL under `<workspace>/sessions` (keyed by `channel:chat_id`).
- `nanobot/agent/memory.py` implements two-layer memory:
  - `memory/MEMORY.md` for persistent facts
  - `memory/HISTORY.md` for append-only searchable timeline
- Consolidation is LLM-driven via a `save_memory` tool contract; session history remains append-only while `last_consolidated` controls what is sent back to model context.

### 4) Provider abstraction and model routing
- Provider metadata is registry-driven in `nanobot/providers/registry.py` (single source of truth).
- Config resolution in `nanobot/config/schema.py` matches model -> provider by explicit prefix, keyword, then fallback.
- CLI provider factory in `nanobot/cli/commands.py` chooses between:
  - LiteLLM provider (most models)
  - direct custom OpenAI-compatible provider
  - OAuth providers (e.g., Codex/Copilot flows)

### 5) Channels and integrations
- Channels are concrete adapters under `nanobot/channels/*.py` (Telegram, Discord, WhatsApp, Feishu, Slack, Email, etc.).
- All channels convert external events into `InboundMessage` and consume `OutboundMessage` for replies.
- WhatsApp is split architecture:
  - Python adapter: `nanobot/channels/whatsapp.py`
  - Node bridge: `bridge/src/*` (Baileys + local WebSocket bridge)

### 6) Scheduled/proactive execution
- `nanobot/cron/service.py` stores jobs in JSON (`~/.nanobot/cron/jobs.json`) and supports `at`, `every`, and cron-expression schedules.
- `nanobot/heartbeat/service.py` periodically evaluates `HEARTBEAT.md`; if tasks exist, it invokes full agent execution and can deliver results to the last active routable channel.

### 7) Managed mode (Control Plane controlled nodes)
- Gateway startup in `nanobot/cli/commands.py` can run in standalone or managed mode.
- Managed mode detection depends on marker/cache/config, then:
  - pulls remote config/policy
  - applies policy filters (including MCP restrictions)
  - establishes control-plane WebSocket message link
  - sends periodic node heartbeats
- Key managed components live under `nanobot/managed/*` and are invoked by CLI command flows (`register`, `gateway`, `agent`).

### 8) Control Plane subsystem
- `control_plane/app.py` builds FastAPI app, initializes DB/admin account, mounts routers, and serves SPA static assets.
- `control_plane/database.py` handles SQLite schema/migrations and persistence.
- `control_plane/routes/*.py` are separated by domain (auth, nodes, policies, llm_keys, tasks, logs, audit, deploy, skill store, feishu gateway).
- `control_plane/frontend` is a Vue 3 + Vite app; build output is served by backend via mounted static files and SPA fallback.

## Important conventions for changes
- Prefer adding new providers by extending provider registry + config schema (not ad-hoc if/else chains).
- Preserve bus-based decoupling between channels and agent loop.
- When modifying session/memory behavior, keep append-only history semantics and `last_consolidated` logic intact.
- In managed mode paths, do not bypass policy filtering or control-plane synchronization logic.