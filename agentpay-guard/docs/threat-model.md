# Threat Model

AgentPay Guard v0.1/v0.2 is a local-first mock payment demo and core library. It partially mitigates control failures around agent payment authority, but it is not production payment infrastructure.

## Partially Mitigated

- Duplicate payment requests through idempotency keys.
- Payment request mutation through request hashes.
- Agent using another agent's mandate through mandate-agent-principal binding checks.
- Missing mandate signer through active principal-user lookup.
- Revoked or expired mandates through policy checks.
- Denylisted merchants and wallets through deterministic policy checks.
- Disallowed merchant, purpose, token, or chain through allowlist checks.
- Double mock execution through single-execute enforcement.
- Stale decisions through execute-time TTL checks.
- Audit tampering after the fact through hash-chain verification.

## Not Solved In v0.1/v0.2

- Real authentication, SSO, MFA, or workspace isolation.
- RBAC enforcement on API routes.
- Concurrent daily-limit race conditions.
- Real wallet ownership proof, DID/VC, or EIP-712 mandate signatures.
- Real x402 or stablecoin payment execution.
- Sanctions, AML, KYB, or KYC vendor screening.
- WORM storage, SIEM export, SOC 2 controls, or enterprise retention.
- Legal or regulatory compliance conclusions.

## Next Hardening Milestones

1. Persistent database with transactional execution and append-only audit writes.
2. Login, workspace separation, API keys, and route-level RBAC.
3. Human approval workflow with approval expiry and audit events.
4. Screening provider interface for demo/manual screening first, vendor integrations later.
5. x402 sandbox adapter that calls AgentPay Guard before payment execution.
