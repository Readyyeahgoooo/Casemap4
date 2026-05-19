# Product Demo

AgentPay Guard is the authority and evidence layer around AI-agent payments. The demo shows three outcomes using mock payments only:

- `approved`: a 5 USDC API-credit payment is within mandate, executes as a mock payment, and produces a receipt.
- `blocked`: a denylisted merchant and wallet are blocked before execution, and a high-risk review case is opened.
- `human-approval`: a 75 USDC request is within the broader mandate but above the automatic approval limit, so it pauses for finance review and does not execute.

## Run

```bash
npm run web
```

Open `http://127.0.0.1:5173`.

For API-only testing:

```bash
npm run api
curl http://127.0.0.1:8787/health
```

## Demo Script

1. Open the approved demo and show `Approved`, `within_mandate`, receipt generated, and audit chain valid.
2. Open the blocked demo and show the denylist triggers, blocked status, case opened, and no execution.
3. Open the human-approval demo and show escalation without mock payment execution.
4. Open the raw evidence tabs and show that the same evidence pack is consumable by developers.

## Positioning

AgentPay Guard does not replace x402, AP2, Coinbase, AWS, Stripe, or stablecoin payment rails. It sits before payment execution to answer:

- Who authorised this agent?
- What was it allowed to buy?
- Was this request inside the mandate?
- What evidence can we show after approval, escalation, or block?
