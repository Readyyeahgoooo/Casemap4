# AgentPay Guard

AgentPay Guard is the open-source core of **AgentPay Compliance OS**: a deterministic mandate, policy, receipt, and audit layer for AI-agent stablecoin payments.

It sits between AI agents and payment rails like x402, checking whether each payment is authorised, within limits, attributable, auditable, and reviewable. v0.1 uses mock payments only, so the core evidence flow can be tested without wallets, private keys, gas, or real stablecoin transfers.

## Quick Start

```bash
cd agentpay-guard
npm run verify
```

Or step by step:

```bash
cd agentpay-guard
npm test
npm run demo:approved
npm run demo:blocked
```

Run the local API:

```bash
cd agentpay-guard
npm run api
```

The API listens on `http://127.0.0.1:8787` and exposes the v0.1 endpoints:

- `GET /health`
- `POST /principals`
- `POST /users`
- `POST /agents`
- `POST /mandates`
- `POST /mandates/:id/revoke`
- `POST /payment-requests/check`
- `POST /payment-requests/:id/execute-mock`
- `GET /receipts/:id`
- `GET /evidence-packs/:payment_request_id`
- `GET /audit-events` (optional filters: `subject_id`, `case_id`, `type`)

## CLI Demo

```bash
node packages/cli/src/cli.js policy:test examples/payment-approved.json
node packages/cli/src/cli.js policy:test examples/payment-blocked.json
node packages/cli/src/cli.js payment:check examples/payment-approved.json
node packages/cli/src/cli.js audit:verify evidence-pack.json
```

The demo flow is:

1. Create a principal, user, agent, and mandate.
2. Submit a payment request with an idempotency key.
3. Run deterministic policy checks.
4. Execute a mock payment only if the decision is approved.
5. Generate a receipt.
6. Export evidence with principal → approver user → agent → mandate → decision → receipt (`approver_user`, `authority_chain_summary`, `scoped_audit_events` for reviewers, `audit_events` for full chain verification).

## Mandate Limits

AgentPay Guard separates automatic approval, human approval, manual review, and hard blocking:

```json
{
  "auto_approve_limit_usd": 20,
  "human_approval_limit_usd": 100,
  "hard_block_limit_usd": 500
}
```

Behavior:

- `amount <= auto_approve_limit_usd`: approved
- `amount > auto_approve_limit_usd && amount <= human_approval_limit_usd`: pending human approval
- `amount > human_approval_limit_usd && amount <= hard_block_limit_usd`: manual review
- `amount > hard_block_limit_usd`: blocked

## What This Is / Is Not

| This is | This is not |
| --- | --- |
| A policy and mandate layer for agent payments | A wallet |
| A receipt and audit evidence generator | A stablecoin issuer |
| A deterministic pre-payment guard | A replacement for x402 or AP2 |
| A developer framework for safer x402/stablecoin flows | A Chainalysis, Elliptic, or TRM replacement |
| A local-first v0.1 mock payment demo | Legal advice |
| A way to produce internal evidence of controls | Proof of regulatory compliance |
| Open-source infrastructure for reviewable agent payments | HKMA-approved software |

## Threat Model

The v0.1 design explicitly considers:

- Agent private key compromise.
- Mandate replay attack.
- Fake merchant domain.
- Forged payment request.
- Webhook spoofing.
- Duplicate payment request.
- Daily limit race condition.
- Revoked mandate still being cached.
- Payment request prompt injection.
- Malicious MCP server asking an agent to pay.
- Tampered audit log.
- Chain reorg or failed transaction.
- Admin account compromise.

The current release partially mitigates a subset of these risks with deterministic policies, mandate status checks, idempotency keys, payment request hashes, mock-only execution with single-execute enforcement and decision TTL checks, denylist/allowlist checks, and hash-chained audit events.

v0.1 does not fully solve daily-limit race conditions under concurrent execution, webhook spoofing, prompt-injection isolation, production RBAC/auth, WORM storage, chain finality handling, or enterprise key custody. Enterprise-grade key custody, webhook signing, access logging, WORM storage, and chain finality handling are later-version work.

## Data Handling

- Do not store private keys.
- Do not put secrets in audit logs.
- Do not send customer data to LLMs by default.
- Redact sensitive metadata where possible.
- Keep v0.1 local-first and mock-payment only.
- Reset demo data by restarting the in-memory process.
- Treat encryption, retention controls, access logs, and field-level redaction as required enterprise features for later releases.

## Roles

The v0.1 model includes the minimum roles even though authentication is local/demo-only:

- `admin`
- `developer`
- `compliance_reviewer`
- `finance_approver`
- `read_only_auditor`

## Idempotency

Every `POST /payment-requests/check` call must include `idempotency_key`. AgentPay Guard computes or accepts a `payment_request_hash` over the payment request details. Reusing the same idempotency key with the same request returns the original decision. Reusing the same key with a different request returns a conflict.

## Project Shape

```text
agentpay-guard/
  apps/api/              Dependency-free local HTTP API
  packages/core/         Mandates, policy decisions, receipts, audit chain
  packages/shared/       Shared validation, roles, hashing helpers
  packages/sdk/          Minimal SDK wrapper
  packages/cli/          policy:test, payment:check, audit:verify
  examples/              Approved and blocked demo scenarios
  tests/                 Node test suite
```

## v0.1 Scope

Included:

- Shared schemas and validation.
- Core mandate service.
- Deterministic policy engine.
- Payment request idempotency.
- Mock payment execution.
- JSON receipt generation.
- Hash-chained audit events.
- Evidence-pack JSON export with approver user and authority chain summary.
- Mandate-agent-principal binding on create and payment check.
- CLI verification.
- Unit tests for the core acceptance criteria.

Deferred:

- Full dashboard.
- Real stablecoin transfers.
- x402 integration.
- DID/VC/EIP-712 mandate signatures.
- OFAC/vendor AML integrations.
- Hosted API.
- SSO, SIEM, WORM storage, and enterprise retention controls.
