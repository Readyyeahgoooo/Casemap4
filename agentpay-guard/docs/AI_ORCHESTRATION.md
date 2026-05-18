# AI Orchestration Workflow

This workflow uses GPT/Codex as architect and final reviewer, DeepSeek-V4-Pro as a bulk implementation/review worker, and a Claude Code-style GitHub loop for rigorous PR review.

## Secret Handling

The DeepSeek key must be provided through the environment:

```bash
export DEEPSEEK_API_KEY="use-a-rotated-key-here"
```

Never commit API keys, paste them into task files, add them to audit logs, or pass them as command-line arguments. If a key has been pasted into chat, rotate it before use.

## DeepSeek Worker

Run a focused worker task:

```bash
cd agentpay-guard
DEEPSEEK_MODEL=deepseek-v4-pro node scripts/deepseek-worker.mjs prompts/deepseek/agentpay-v01-review.md
```

Default settings:

- Base URL: `https://api.deepseek.com`
- Model: `deepseek-v4-pro`
- Temperature: `0.2`

DeepSeek is used for bounded tasks only: implementation tickets, patch review, test gap discovery, and README clarity review. It should not approve payment-policy behavior by itself.

## Claude Code-Style GitHub Loop

Use this PR workflow:

1. Open a branch for a narrow ticket, such as `codex/agentpay-v01-core`.
2. Keep each PR scoped to one behavior slice: policy engine, idempotency, receipt/evidence, CLI, docs, or API.
3. Require CI to pass before review.
4. Ask Claude/GitHub reviewer to check wording, threat model, data handling, and overclaim risk.
5. Ask GPT/Codex to check architecture, deterministic behavior, API/schema compatibility, and tests.
6. Merge only after test results and review findings are summarized in the PR.

Suggested PR comment prompt:

```text
@claude Please review this PR for compliance wording, overclaim risk, threat model completeness, data-handling clarity, and whether the evidence pack is understandable to a finance/compliance reviewer. Do not suggest real-money payment integration for v0.1.
```

## GitHub Checks

The repo includes a path-scoped GitHub Actions workflow for `agentpay-guard`. It runs:

```bash
npm test
```

The workflow intentionally avoids secrets. DeepSeek and Claude API keys should be stored only in GitHub Actions secrets if an explicit automated AI review workflow is later added.

## Review Responsibilities

GPT/Codex:

- Architecture consistency.
- API/schema compatibility.
- Policy determinism.
- Idempotency and duplicate request behavior.
- Test coverage and acceptance criteria.

DeepSeek-V4-Pro:

- Bulk implementation tickets.
- Patch risk discovery.
- Missing test suggestions.
- Focused README and DX improvements.

Claude Code-style reviewer:

- README clarity.
- Compliance wording.
- Legal/regulatory overclaim risk.
- Threat model and data-handling language.
- Evidence-pack narrative quality.
