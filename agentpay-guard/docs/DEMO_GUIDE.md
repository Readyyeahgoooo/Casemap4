# AgentPay Guard — Live LLM Agent Demo Guide

This guide walks you through an **offline, investor-style demo**: three autonomous agents propose purchases, **AgentPay Guard** approves/blocks/reviews them in real time, and the **web console** shows live results plus evidence packs.

> **Honest scope:** mock settlement only, demo OFAC list (not live sanctions), optional LLM (OpenAI/Anthropic) with automatic offline fallback. No mainnet payments.

---

## What you are demonstrating

| # | Investor question | What happens in this demo |
|---|-------------------|---------------------------|
| 1 | Are these real agents? | Three Node processes (**ProcurementBot**, **ResearchBot**, **TravelBot**) plan purchases and call the live API. |
| 2 | Does control work? | Guard returns `approved`, `blocked`, or `pending_human_approval` / `manual_review`. Agents **obey** (execute mock pay only when approved). |
| 3 | Can I see it live? | Web **Live Agent Feed** polls every 2s; click any event to open its evidence pack. |
| 4 | Is evidence verifiable? | Hash-linked audit chain, mandate signatures, **Re-verify audit chain** button. |

---

## Prerequisites

- **Node.js 22+**
- Repo: `cd agentpay-guard`
- Install: `npm test` (sanity check)

### Optional — real LLM planning

Without API keys, agents use a **local catalog heuristic** (still non-scripted outcomes — Guard decides).

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."
export AGENTPAY_LLM_PROVIDER=openai   # optional; auto-detected if key set

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
export AGENTPAY_LLM_PROVIDER=anthropic
```

---

## Quick start (3 terminals — recommended for investors)

### Terminal 1 — API + web console

```bash
cd agentpay-guard
npm run web
```

Open **http://127.0.0.1:5173** → scroll to **Live Agent Feed**.

Optional persistence:

```bash
export AGENTPAY_STORE=sqlite
export AGENTPAY_DB_PATH=./data/agentpay.db
npm run web
```

### Terminal 2 — seed the demo world (once per server restart)

```bash
cd agentpay-guard
npm run demo:seed
```

Creates **Acme Demo Holdings** + three agents/mandates. Registry saved to `data/demo-agents-registry.json`.

You can also click **Seed demo agents** in the web UI.

### Terminal 3 — run all agents

**Option A — one supervisor (easiest):**

```bash
cd agentpay-guard
npm run demo:agents
```

**Option B — three terminals (most impressive visually):**

```bash
npm run demo:agent:procurement
npm run demo:agent:research
npm run demo:agent:travel
```

**One-shot test (no loop):**

```bash
npm run demo:agents:once
```

---

## What each agent does

| Agent | Typical behavior | Often triggers |
|-------|------------------|----------------|
| **ProcurementBot** | Office supplies, low amounts | `approved` |
| **ResearchBot** | API/data vendors; may pick risky merchant/wallet | `blocked` (OFAC demo / denylist) |
| **TravelBot** | Hotels/flights, higher amounts | `pending_human_approval` |

Agents do **not** know the outcome in advance. Guard + mandate + screening decide.

---

## Live results in the browser

1. **Live Agent Feed** — streaming cards (approve/block/review).
2. **Stats row** — per-agent approved / blocked / review counts.
3. **Click a card** — loads that payment’s **evidence pack** below (authority chain, rules, audit).
4. **Re-verify audit chain** — confirms ledger integrity.
5. **Demo Quick Actions** — classic canned scenarios (approved / blocked / human approval) for scripted walkthrough.

Feed API (for custom dashboards):

```bash
curl http://127.0.0.1:5173/demo/live-feed
curl -X POST http://127.0.0.1:5173/demo/seed-agents
```

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENTPAY_API_URL` | `http://127.0.0.1:5173` | Agents → API base URL |
| `AGENTPAY_AGENT_INTERVAL_MS` | `12000`–`16000` | Delay between agent purchase cycles |
| `AGENTPAY_LLM_PROVIDER` | auto | `openai`, `anthropic`, or `heuristic` |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | — | Enable real LLM planning |
| `AGENTPAY_API_KEY` | — | If set, agents must send `x-agentpay-api-key` header |

---

## Step-by-step test checklist (before investors)

1. `npm test` — all green.
2. `npm run web` — health pill shows **API healthy**.
3. `npm run demo:seed` — three agents listed.
4. `npm run demo:agents:once` — terminal shows plan → decision → obey.
5. Browser — Live Feed updates; click event → evidence pack loads.
6. Run **Re-verify audit chain** — Valid.
7. Optional: set `OPENAI_API_KEY`, restart agents — logs show `openai` provider.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `API unreachable` in browser | Start `npm run web` first. |
| Agents fail to connect | Match `AGENTPAY_API_URL` to server port (5173 for `npm run web`). |
| Empty Live Feed | Run `npm run demo:seed`, then start agents. |
| All requests 401 | Export same `AGENTPAY_API_KEY` for server and agents. |
| SQLite locked | One API process only; remove stale `data/agentpay.db` if needed. |

---

## npm scripts reference

| Script | Description |
|--------|-------------|
| `npm run web` | API + evidence console on port 5173 |
| `npm run api` | API only on port 8787 |
| `npm run demo:seed` | Seed Acme + 3 agents |
| `npm run demo:agents` | Run all agents (parallel loops) |
| `npm run demo:agents:once` | One purchase per agent |
| `npm run demo:agent:procurement` | ProcurementBot only |
| `npm run demo:agent:research` | ResearchBot only |
| `npm run demo:agent:travel` | TravelBot only |

---

## Positioning line for investors

> “These agents are making real API payment requests. Guard is the authority layer: mandate, policy, screening, and tamper-evident audit — before any stablecoin rail. Today we mock settlement; the control and evidence are real.”
