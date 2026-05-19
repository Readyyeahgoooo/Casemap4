import assert from "node:assert/strict";
import test from "node:test";
import { createAgentPayApi, readBody } from "../apps/api/src/server.js";
import { AgentPayGuard } from "../packages/core/src/index.js";
import { canonicalize, sha256 } from "../packages/shared/src/hash.js";
import { parseIsoDurationMs } from "../packages/shared/src/duration.js";
import { mandateHash, signMandateHash, verifyMandateSignature } from "../packages/shared/src/mandate-sign.js";
import { normalizeDomain } from "../packages/shared/src/schemas.js";

function setup() {
  const guard = new AgentPayGuard({ now: () => new Date("2026-05-17T04:30:00.000Z") });
  const principal = guard.createPrincipal({
    type: "company",
    legal_name: "ABC Trading Limited",
    jurisdiction: "HK"
  });
  const user = guard.createUser({
    principal_id: principal.id,
    email: "finance_manager@abc.example",
    role: "finance_approver"
  });
  const agent = guard.createAgent({
    principal_id: principal.id,
    name: "ResearchBuyerBot",
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
    expires_at: "2026-06-30T23:59:59.000Z",
    signed_by: user.email
  });
  return { guard, principal, user, agent, mandate };
}

function request(overrides = {}) {
  return {
    merchant: "api.vendor.com",
    amount_usd: "5.00",
    token: "USDC",
    chain: "base",
    purpose: "buy_api_credits",
    merchant_request_id: "vendor_req_001",
    nonce: "nonce_001",
    idempotency_key: "idem_001",
    ...overrides
  };
}

function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ baseUrl: `http://127.0.0.1:${port}`, close: () => new Promise((r) => server.close(r)) });
    });
  });
}

test("malformed decision_ttl is rejected during checkPayment", () => {
  const { guard, agent, mandate } = setup();
  assert.throws(
    () =>
      guard.checkPayment({
        ...request({ decision_ttl: "not-a-duration", idempotency_key: "idem_bad_ttl" }),
        agent_id: agent.id,
        mandate_id: mandate.id
      }),
    /Invalid decision_ttl/
  );
});

test("parseIsoDurationMs rejects out-of-range ttl", () => {
  assert.throws(() => parseIsoDurationMs("PT25H"), /out of allowed range/);
});

test("rejects replayed merchant_request_id with a fresh idempotency key", () => {
  const { guard, agent, mandate } = setup();
  guard.checkPayment({
    ...request({ idempotency_key: "idem_replay_merchant_1" }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });

  assert.throws(
    () =>
      guard.checkPayment({
        ...request({
          idempotency_key: "idem_replay_merchant_2",
          nonce: "nonce_replay_2"
        }),
        agent_id: agent.id,
        mandate_id: mandate.id
      }),
    /merchant_request_id was already used/
  );
});

test("rejects replayed nonce with a fresh idempotency key", () => {
  const { guard, agent, mandate } = setup();
  guard.checkPayment({
    ...request({
      idempotency_key: "idem_replay_nonce_1",
      merchant_request_id: "vendor_req_a"
    }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });

  assert.throws(
    () =>
      guard.checkPayment({
        ...request({
          idempotency_key: "idem_replay_nonce_2",
          merchant_request_id: "vendor_req_b",
          nonce: "nonce_001"
        }),
        agent_id: agent.id,
        mandate_id: mandate.id
      }),
    /nonce was already used/
  );
});

test("mandate signature verifies and detects tampering", () => {
  const { mandate } = setup();
  assert.equal(verifyMandateSignature(mandate).valid, true);

  const tampered = {
    ...mandate,
    signature: mandate.signature.slice(0, -2) + "aa"
  };
  assert.equal(verifyMandateSignature(tampered).valid, false);
});

test("demo signing private keys stay internal", () => {
  const { guard, user, agent, mandate } = setup();
  assert.equal(user.signing_private_key, undefined);
  assert.ok(user.signing_public_key);

  const checked = guard.checkPayment({
    ...request({ idempotency_key: "idem_private_key_redaction" }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });
  const pack = guard.exportEvidencePack(checked.payment_request.id);
  assert.equal(pack.approver_user.signing_private_key, undefined);
  assert.doesNotMatch(JSON.stringify(pack), /signing_private_key/);

  const storedUser = guard.store.users.get(user.id);
  const userCreatedEvent = guard.store.auditEvents.find((event) => event.type === "USER_CREATED");
  assert.ok(storedUser.signing_private_key);
  assert.equal(userCreatedEvent.output_hash, sha256(user));
  assert.notEqual(userCreatedEvent.output_hash, sha256(storedUser));
});

test("provided private signing keys are redacted before audit hashing", () => {
  const guard = new AgentPayGuard({ now: () => new Date("2026-05-17T04:30:00.000Z") });
  const principal = guard.createPrincipal({
    type: "company",
    legal_name: "ABC Trading Limited",
    jurisdiction: "HK"
  });
  const input = {
    principal_id: principal.id,
    email: "external_signer@abc.example",
    role: "finance_approver",
    signing_public_key: "demo-public-key",
    signing_private_key: "demo-private-key"
  };
  const user = guard.createUser(input);
  const event = guard.store.auditEvents.find((item) => item.type === "USER_CREATED");

  assert.equal(user.signing_private_key, undefined);
  assert.equal(event.input_hash, sha256({ ...input, signing_private_key: undefined }));
  assert.notEqual(event.input_hash, sha256(input));
});

test("decision stores mandate_hash and evidence pack reports integrity", () => {
  const { guard, agent, mandate } = setup();
  const checked = guard.checkPayment({
    ...request({ idempotency_key: "idem_mandate_hash_evidence" }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });

  assert.ok(checked.decision.mandate_hash);
  assert.equal(checked.decision.mandate_hash, mandate.mandate_hash);

  const pack = guard.exportEvidencePack(checked.payment_request.id);
  assert.equal(pack.mandate_integrity.mandate_hash_at_decision, mandate.mandate_hash);
  assert.equal(pack.mandate_integrity.mandate_hash_matches, true);
  assert.equal(pack.mandate_integrity.mandate_signature_valid, true);
});

test("canonical hash ordering is stable across key insertion order", () => {
  const left = sha256({ z: 1, a: 2, m: 3 });
  const right = sha256({ m: 3, z: 1, a: 2 });
  assert.equal(left, right);
  assert.match(canonicalize({ b: 2, a: 1 }), /"a":1,"b":2/);
});

test("normalizeDomain converts IDN hostnames to ASCII", () => {
  assert.equal(normalizeDomain("münchen.de"), "xn--mnchen-3ya.de");
});

test("invalid EVM wallet is rejected", () => {
  const { guard, principal } = setup();
  assert.throws(
    () =>
      guard.createAgent({
        principal_id: principal.id,
        name: "BadWalletBot",
        type: "autonomous_api_buyer",
        wallet_address: "0x123",
        chain: "base"
      }),
    /Invalid EVM wallet address/
  );
});

test("readBody rejects payloads larger than 1MB", async () => {
  const requestLike = {
    async *[Symbol.asyncIterator]() {
      yield Buffer.alloc(1_000_001, "a");
    }
  };

  await assert.rejects(() => readBody(requestLike), /Request body too large/);
});

test("API key is required for protected routes when configured", async () => {
  const server = createAgentPayApi(new AgentPayGuard(), { apiKey: "test-secret-key" });
  const { baseUrl, close } = await listen(server);
  try {
    const health = await fetch(`${baseUrl}/health`);
    assert.equal(health.status, 200);

    const blocked = await fetch(`${baseUrl}/principals`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ type: "company", legal_name: "X", jurisdiction: "HK" })
    });
    assert.equal(blocked.status, 401);

    const allowed = await fetch(`${baseUrl}/principals`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-agentpay-api-key": "test-secret-key"
      },
      body: JSON.stringify({ type: "company", legal_name: "Y", jurisdiction: "HK" })
    });
    assert.equal(allowed.status, 201);
  } finally {
    await close();
  }
});

test("scoped API keys enforce route-level roles", async () => {
  const server = createAgentPayApi(new AgentPayGuard(), {
    apiKeys: new Map([
      ["admin-key", ["admin"]],
      ["developer-key", ["developer"]],
      ["auditor-key", ["read_only_auditor"]]
    ])
  });
  const { baseUrl, close } = await listen(server);
  try {
    const developerCreatePrincipal = await fetch(`${baseUrl}/principals`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-agentpay-api-key": "developer-key"
      },
      body: JSON.stringify({ type: "company", legal_name: "X", jurisdiction: "HK" })
    });
    assert.equal(developerCreatePrincipal.status, 403);

    const adminCreatePrincipal = await fetch(`${baseUrl}/principals`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-agentpay-api-key": "admin-key"
      },
      body: JSON.stringify({ type: "company", legal_name: "Y", jurisdiction: "HK" })
    });
    assert.equal(adminCreatePrincipal.status, 201);

    const developerAuditRead = await fetch(`${baseUrl}/audit-events`, {
      headers: { "x-agentpay-api-key": "developer-key" }
    });
    assert.equal(developerAuditRead.status, 403);

    const auditorAuditRead = await fetch(`${baseUrl}/audit-events`, {
      headers: { "x-agentpay-api-key": "auditor-key" }
    });
    assert.equal(auditorAuditRead.status, 200);
  } finally {
    await close();
  }
});

test("oversized HTTP body returns 413", async () => {
  const server = createAgentPayApi(new AgentPayGuard());
  const { baseUrl, close } = await listen(server);
  try {
    const response = await fetch(`${baseUrl}/principals`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "a".repeat(1_000_001)
    });
    assert.equal(response.status, 413);
  } finally {
    await close();
  }
});

test("mandate hash changes when mandate payload changes", () => {
  const { mandate } = setup();
  const original = mandate.mandate_hash;
  const changed = mandateHash({ ...mandate, limits: { ...mandate.limits, auto_approve_limit_usd: 99 } });
  assert.notEqual(original, changed);
});
