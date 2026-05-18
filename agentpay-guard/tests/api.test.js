import assert from "node:assert/strict";
import test from "node:test";
import { AgentPayGuard } from "../packages/core/src/index.js";
import { createAgentPayApi } from "../apps/api/src/server.js";

function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ baseUrl: `http://127.0.0.1:${port}`, close: () => new Promise((r) => server.close(r)) });
    });
  });
}

async function request(baseUrl, path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, options);
  const body = await response.json();
  return { status: response.status, body };
}

test("API /health returns ok", async () => {
  const guard = new AgentPayGuard();
  const server = createAgentPayApi(guard);
  const { baseUrl, close } = await listen(server);
  try {
    const result = await request(baseUrl, "/health");
    assert.equal(result.status, 200);
    assert.deepEqual(result.body, { status: "ok" });
  } finally {
    await close();
  }
});

test("API /audit-events filters by subject_id", async () => {
  const guard = new AgentPayGuard();
  const principal = guard.createPrincipal({
    type: "company",
    legal_name: "API Test Co",
    jurisdiction: "HK"
  });
  const user = guard.createUser({
    principal_id: principal.id,
    email: "ops@example.com",
    role: "finance_approver"
  });
  const agent = guard.createAgent({
    principal_id: principal.id,
    name: "ApiBot",
    type: "autonomous_api_buyer",
    wallet_address: "0xabc0000000000000000000000000000000000001",
    chain: "base"
  });
  const mandate = guard.createMandate({
    agent_id: agent.id,
    principal_id: principal.id,
    allowed_actions: ["buy_api_credits"],
    allowed_merchants: ["api.vendor.com"],
    allowed_tokens: ["USDC"],
    allowed_chains: ["base"],
    limits: {
      auto_approve_limit_usd: 20,
      human_approval_limit_usd: 100,
      hard_block_limit_usd: 500
    },
    expires_at: "2027-06-30T23:59:59.000Z",
    signed_by: user.email
  });

  const checked = guard.checkPayment({
    agent_id: agent.id,
    mandate_id: mandate.id,
    merchant: "api.vendor.com",
    amount_usd: "5.00",
    token: "USDC",
    chain: "base",
    purpose: "buy_api_credits",
    idempotency_key: "api_idem_1"
  });
  const paymentRequestId = checked.payment_request.id;

  const server = createAgentPayApi(guard);
  const { baseUrl, close } = await listen(server);
  try {
    const all = await request(baseUrl, "/audit-events");
    const filtered = await request(baseUrl, `/audit-events?subject_id=${paymentRequestId}`);
    assert.equal(all.status, 200);
    assert.equal(filtered.status, 200);
    assert.ok(all.body.length > filtered.body.length);
    assert.ok(filtered.body.length >= 1);
    assert.ok(filtered.body.every((event) => event.subject_id === paymentRequestId));
  } finally {
    await close();
  }
});

test("API invalid JSON returns JSON error", async () => {
  const server = createAgentPayApi(new AgentPayGuard());
  const { baseUrl, close } = await listen(server);
  try {
    const response = await fetch(`${baseUrl}/principals`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{not-json"
    });
    const body = await response.json();
    assert.equal(response.status, 400);
    assert.equal(body.error, "ValidationError");
    assert.match(body.message, /Invalid JSON/);
  } finally {
    await close();
  }
});
