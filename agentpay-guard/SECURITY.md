# Security Policy

AgentPay Guard v0.1/v0.2 is mock-payment software. Do not use it to custody private keys, execute real payments, or make legal/regulatory compliance claims.

## Reporting Issues

Please report vulnerabilities privately to the maintainers before public disclosure.

Include:

- Affected version or commit.
- Reproduction steps.
- Expected and actual behavior.
- Any logs or evidence needed to validate the issue.

## Sensitive Data

- Do not store private keys in this repo or in demo data.
- Do not commit API keys, wallet seed phrases, access tokens, or customer secrets.
- Do not put secrets in audit events.
- Demo mandate-signing private keys are generated in-memory and redacted from evidence/API responses; replace this with real key custody before any non-local pilot.
- Rotate any credential that may have been exposed.

## Current Limits

The current release includes scoped API-key route checks for local pilots, but does not include production login/SSO, workspace isolation, persistent storage, WORM retention, real sanctions/AML screening, wallet ownership proof, or real stablecoin execution. Treat all demos as local evidence-flow prototypes.
