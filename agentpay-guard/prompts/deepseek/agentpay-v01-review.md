# DeepSeek-V4-Pro Worker Task: AgentPay Guard v0.1 Review

You are reviewing the local `agentpay-guard` v0.1 implementation.

## Product Goal

AgentPay Guard is a deterministic mandate, policy, receipt, and audit layer for AI-agent stablecoin payments. v0.1 must prove the vertical slice:

`mandate -> policy decision -> mock payment -> receipt -> audit evidence`

No real wallet, stablecoin transfer, paid AML vendor, x402 integration, or regulatory compliance claim is required for v0.1.

## Review Scope

Review for:

- Policy determinism.
- Idempotency correctness.
- Duplicate payment request behavior.
- Mandate limit behavior.
- Mock payment execution safety.
- Receipt completeness.
- Audit hash-chain integrity.
- Evidence-pack usefulness.
- README overclaim risk.

## Required Output

Return:

1. Top 5 concrete issues or risks, ordered by severity.
2. Exact file/function references where possible.
3. A small patch plan for each issue.
4. Any tests that should be added.

Do not rewrite the whole project. Do not suggest real-money payment integration for v0.1.
