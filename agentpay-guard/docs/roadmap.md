# Roadmap

## Milestone 1: GitHub Visual Demo

- Evidence Pack Viewer.
- Authority Chain.
- Rule Checklist.
- Audit Timeline.
- Raw JSON tabs.
- Approved, blocked, and human-approval scenarios.

Status: implemented as a dependency-free local web app served by `npm run web`.

## Milestone 2: Persistent Backend

- SQLite or Postgres.
- Prisma or Drizzle migrations.
- Workspace IDs.
- Database-backed audit events.
- Docker Compose.

## Milestone 3: Human Approval

- Approval queue.
- Approve/reject action.
- Reviewer notes.
- Approval expiry.
- Execution only after valid approval.

## Milestone 4: Auth And RBAC

- Login.
- Workspace separation.
- API keys.
- Role checks for agent, mandate, approval, case review, evidence export, and policy changes.

Status: route-level scoped API keys are implemented for the local API. Real login, workspace isolation, user sessions, and enterprise RBAC remain deferred.

## Milestone 5: x402 Sandbox

- Mock x402 endpoint.
- Guard-before-payment middleware.
- Testnet or sandbox adapter after the mock flow is stable.

## Milestone 6: Screening Hooks

- `screenMerchant()`.
- `screenWallet()`.
- `screenPrincipal()`.
- `screenUser()`.
- Demo provider first, vendor adapters later.

Status: a demo payment-request screening provider is implemented for merchant and wallet clear/flagged results. Real sanctions-list ingestion and vendor adapters remain deferred.

## Milestone 7: Corporate Pilot Pack

- Docker deployment.
- OpenAPI docs.
- Security policy.
- Data handling document.
- Demo video and screenshots.
