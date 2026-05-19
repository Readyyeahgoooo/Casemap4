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
- Demo signing private key exposure through public-output and audit-hash redaction.
- Route misuse through scoped API-key role checks when `AGENTPAY_API_KEYS` is configured.
- Basic screening extensibility through the demo `ScreeningProvider` interface.
- Audit tampering after the fact through hash-chain verification.

## Not Solved In v0.1/v0.2

- Real login, SSO, MFA, or workspace isolation.
- Enterprise RBAC with user sessions, policy administration, and approval delegation.
- Concurrent daily-limit race conditions.
- Real wallet ownership proof, DID/VC, or EIP-712 mandate signatures.
- Real x402 or stablecoin payment execution.
- Real sanctions, AML, KYB, or KYC vendor screening beyond demo hooks.
- WORM storage, SIEM export, SOC 2 controls, or enterprise retention.
- Legal or regulatory compliance conclusions.

## Next Hardening Milestones

1. Persistent database with transactional execution and append-only audit writes.
2. Login, workspace separation, API keys, and enterprise RBAC.
3. Human approval workflow with approval expiry and audit events.
4. OFAC/OpenSanctions-style ingestion and vendor screening adapters.
5. x402 sandbox adapter that calls AgentPay Guard before payment execution.
