import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { AgentPayGuard, createDemoScreeningProvider } from "../packages/core/src/index.js";
import { createStore } from "../packages/core/src/store-factory.js";

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
    denied_merchants: ["blocked.vendor.com"],
    allowed_tokens: ["USDC"],
    allowed_chains: ["base"],
    denied_wallets: ["0xdead000000000000000000000000000000000000"],
    limits: {
      auto_approve_limit_usd: 20,
      human_approval_limit_usd: 100,
      hard_block_limit_usd: 500,
      daily_limit_usd: 1000
    },
    expires_at: "2026-06-30T23:59:59.000Z",
    signed_by: user.email
  });
  return { guard, principal, user, agent, mandate };
}

function request(overrides = {}) {
  const idempotency_key = overrides.idempotency_key ?? "idem_001";
  return {
    merchant: "api.vendor.com",
    amount_usd: "5.00",
    token: "USDC",
    chain: "base",
    purpose: "buy_api_credits",
    merchant_request_id: overrides.merchant_request_id ?? `vendor_${idempotency_key}`,
    nonce: overrides.nonce ?? `nonce_${idempotency_key}`,
    idempotency_key,
    ...overrides
  };
}

test("approves a payment within mandate and generates receipt/evidence", () => {
  const { guard, agent, principal, mandate } = setup();
  const checked = guard.checkPayment({ ...request(), agent_id: agent.id, mandate_id: mandate.id });
  assert.equal(checked.decision.status, "approved");
  assert.equal(checked.decision.reason, "within_mandate");

  const executed = guard.executeMockPayment(checked.payment_request.id);
  assert.equal(executed.receipt.mandate_id, mandate.id);
  assert.equal(executed.receipt.agent_id, agent.id);
  assert.equal(executed.receipt.principal, principal.legal_name);
  assert.equal(executed.receipt.merchant, "api.vendor.com");
  assert.equal(executed.receipt.amount_usd, "5.00");
  assert.equal(executed.receipt.token, "USDC");
  assert.equal(executed.receipt.chain, "base");
  assert.equal(executed.receipt.purpose, "buy_api_credits");
  assert.equal(executed.receipt.screening_status, "clear");
  assert.ok(executed.receipt.decision_id);
  assert.ok(executed.receipt.tx_hash);

  const pack = guard.exportEvidencePack(checked.payment_request.id);
  assert.equal(pack.mandate.id, mandate.id);
  assert.equal(pack.payment_request.id, checked.payment_request.id);
  assert.equal(pack.decision.id, checked.decision.id);
  assert.equal(pack.receipt.id, executed.receipt.id);
  assert.ok(pack.audit_events.length >= 1);
  assert.ok(Array.isArray(pack.scoped_audit_events));
  assert.ok(pack.scoped_audit_events.length >= 1);
  assert.ok(pack.scoped_audit_events.length <= pack.audit_events.length);
  assert.equal(pack.audit_verification.valid, true);
});

test("returns pending_human_approval above auto limit and within approval limit", () => {
  const { guard, agent, mandate } = setup();
  const checked = guard.checkPayment({ ...request({ amount_usd: "75.00", idempotency_key: "idem_approval" }), agent_id: agent.id, mandate_id: mandate.id });
  assert.equal(checked.decision.status, "pending_human_approval");
  assert.equal(checked.decision.approval_required, true);
});

test("returns manual_review between human approval limit and hard block limit", () => {
  const { guard, agent, mandate } = setup();
  const checked = guard.checkPayment({ ...request({ amount_usd: "250.00", idempotency_key: "idem_review" }), agent_id: agent.id, mandate_id: mandate.id });
  assert.equal(checked.decision.status, "manual_review");
});

test("blocks above hard block limit", () => {
  const { guard, agent, mandate } = setup();
  const checked = guard.checkPayment({ ...request({ amount_usd: "501.00", idempotency_key: "idem_hard_block" }), agent_id: agent.id, mandate_id: mandate.id });
  assert.equal(checked.decision.status, "blocked");
  assert.equal(checked.decision.reason, "hard_block_limit_exceeded");
});

test("blocks expired and revoked mandates", () => {
  const expired = setup();
  const expiredMandate = expired.guard.createMandate({
    ...expired.mandate,
    id: undefined,
    expires_at: "2026-01-01T00:00:00.000Z"
  });
  const expiredDecision = expired.guard.checkPayment({ ...request({ idempotency_key: "idem_expired" }), agent_id: expired.agent.id, mandate_id: expiredMandate.id });
  assert.equal(expiredDecision.decision.status, "blocked");
  assert.equal(expiredDecision.decision.reason, "mandate_expired");

  const revoked = setup();
  revoked.guard.revokeMandate(revoked.mandate.id);
  const revokedDecision = revoked.guard.checkPayment({ ...request({ idempotency_key: "idem_revoked" }), agent_id: revoked.agent.id, mandate_id: revoked.mandate.id });
  assert.equal(revokedDecision.decision.status, "blocked");
  assert.equal(revokedDecision.decision.reason, "mandate_not_active");
});

test("blocks disallowed merchant, token, chain, denylisted merchant, and wallet", () => {
  const { guard, agent, mandate } = setup();
  assert.equal(guard.checkPayment({ ...request({ merchant: "unknown.vendor.com", idempotency_key: "idem_merchant" }), agent_id: agent.id, mandate_id: mandate.id }).decision.status, "blocked");
  assert.equal(guard.checkPayment({ ...request({ purpose: "purchase_dataset", idempotency_key: "idem_purpose" }), agent_id: agent.id, mandate_id: mandate.id }).decision.reason, "purpose_not_allowed");
  assert.equal(guard.checkPayment({ ...request({ token: "ETH", idempotency_key: "idem_token" }), agent_id: agent.id, mandate_id: mandate.id }).decision.status, "blocked");
  assert.equal(guard.checkPayment({ ...request({ chain: "solana", idempotency_key: "idem_chain" }), agent_id: agent.id, mandate_id: mandate.id }).decision.status, "blocked");
  assert.equal(
    guard.checkPayment({
      ...request({ merchant: "blocked.vendor.com", idempotency_key: "idem_denied_merchant" }),
      agent_id: agent.id,
      mandate_id: mandate.id
    }).decision.reason,
    "screening_hit"
  );
  assert.equal(
    guard.checkPayment({
      ...request({
        counterparty_wallet_address: "0xdead000000000000000000000000000000000000",
        idempotency_key: "idem_wallet"
      }),
      agent_id: agent.id,
      mandate_id: mandate.id
    }).decision.reason,
    "screening_hit"
  );
});

test("screening provider can block an otherwise allowed payment", () => {
  const guard = new AgentPayGuard({
    now: () => new Date("2026-05-17T04:30:00.000Z"),
    screeningProvider: createDemoScreeningProvider({
      flaggedMerchants: ["api.vendor.com"]
    })
  });
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
  const checked = guard.checkPayment({
    ...request({ idempotency_key: "idem_screening_hit" }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });

  assert.equal(checked.decision.status, "blocked");
  assert.equal(checked.decision.reason, "screening_hit");
  assert.equal(checked.decision.screening_status, "flagged");
  assert.equal(checked.decision.screening_provider, "demo_screening_v0.2");
  assert.ok(checked.decision.rules_triggered.some((rule) => rule.id === "block_screening_result"));
});

test("handles idempotency and rejects conflicting reuse", () => {
  const { guard, agent, mandate } = setup();
  const first = guard.checkPayment({ ...request(), agent_id: agent.id, mandate_id: mandate.id });
  const second = guard.checkPayment({ ...request(), agent_id: agent.id, mandate_id: mandate.id });
  assert.equal(second.idempotent, true);
  assert.equal(second.decision.id, first.decision.id);

  assert.throws(
    () => guard.checkPayment({ ...request({ amount_usd: "6.00" }), agent_id: agent.id, mandate_id: mandate.id }),
    /idempotency_key was reused/
  );

  assert.throws(
    () => guard.checkPayment({ ...request({ idempotency_key: "idem_bad_hash", payment_request_hash: "sha256:not-real" }), agent_id: agent.id, mandate_id: mandate.id }),
    /payment_request_hash does not match/
  );
});

test("mock payment cannot execute unless decision is approved", () => {
  const { guard, agent, mandate } = setup();
  const checked = guard.checkPayment({ ...request({ amount_usd: "75.00", idempotency_key: "idem_no_execute" }), agent_id: agent.id, mandate_id: mandate.id });
  assert.equal(checked.decision.status, "pending_human_approval");
  assert.throws(() => guard.executeMockPayment(checked.payment_request.id), /only execute after an approved decision/);
});

test("mock payment cannot execute twice", () => {
  const { guard, agent, mandate } = setup();
  const checked = guard.checkPayment({
    ...request({ idempotency_key: "idem_double_execute" }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });
  assert.equal(checked.decision.status, "approved");
  const first = guard.executeMockPayment(checked.payment_request.id);
  assert.ok(first.payment.tx_hash);
  assert.equal(guard.store.paymentRequests.get(checked.payment_request.id).status, "executed");
  assert.throws(
    () => guard.executeMockPayment(checked.payment_request.id),
    /already executed/
  );
});

test("amount boundaries are exact", () => {
  const { guard, agent, mandate } = setup();
  assert.equal(
    guard.checkPayment({
      ...request({ amount_usd: "20.00", idempotency_key: "idem_boundary_20_00" }),
      agent_id: agent.id,
      mandate_id: mandate.id
    }).decision.status,
    "approved"
  );
  assert.equal(
    guard.checkPayment({
      ...request({ amount_usd: "20.01", idempotency_key: "idem_boundary_20_01" }),
      agent_id: agent.id,
      mandate_id: mandate.id
    }).decision.status,
    "pending_human_approval"
  );
  assert.equal(
    guard.checkPayment({
      ...request({ amount_usd: "100.00", idempotency_key: "idem_boundary_100_00" }),
      agent_id: agent.id,
      mandate_id: mandate.id
    }).decision.status,
    "pending_human_approval"
  );
  assert.equal(
    guard.checkPayment({
      ...request({ amount_usd: "100.01", idempotency_key: "idem_boundary_100_01" }),
      agent_id: agent.id,
      mandate_id: mandate.id
    }).decision.status,
    "manual_review"
  );
  assert.equal(
    guard.checkPayment({
      ...request({ amount_usd: "500.00", idempotency_key: "idem_boundary_500_00" }),
      agent_id: agent.id,
      mandate_id: mandate.id
    }).decision.status,
    "manual_review"
  );
  assert.equal(
    guard.checkPayment({
      ...request({ amount_usd: "500.01", idempotency_key: "idem_boundary_500_01" }),
      agent_id: agent.id,
      mandate_id: mandate.id
    }).decision.status,
    "blocked"
  );
});

test("daily limit blocks when approved total would exceed daily limit", () => {
  const { guard, agent, principal, user } = setup();
  const mandate = guard.createMandate({
    agent_id: agent.id,
    principal_id: principal.id,
    allowed_actions: ["buy_api_credits"],
    allowed_merchants: ["api.vendor.com"],
    allowed_tokens: ["USDC"],
    allowed_chains: ["base"],
    limits: {
      auto_approve_limit_usd: 1000,
      human_approval_limit_usd: 2000,
      hard_block_limit_usd: 5000,
      daily_limit_usd: 1000
    },
    expires_at: "2026-06-30T23:59:59.000Z",
    signed_by: user.email
  });

  const first = guard.checkPayment({
    ...request({ amount_usd: "995.00", idempotency_key: "idem_daily_995" }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });
  assert.equal(first.decision.status, "approved");

  const second = guard.checkPayment({
    ...request({
      amount_usd: "5.00",
      idempotency_key: "idem_daily_1000",
      nonce: "nonce_daily_2"
    }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });
  assert.equal(second.decision.status, "approved");

  const third = guard.checkPayment({
    ...request({
      amount_usd: "0.01",
      idempotency_key: "idem_daily_1000_01",
      nonce: "nonce_daily_3"
    }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });
  assert.equal(third.decision.status, "blocked");
  assert.equal(third.decision.reason, "daily_limit_exceeded");
});

test("expired decision ttl cannot execute", () => {
  const guard = new AgentPayGuard({
    now: () => new Date("2026-05-17T04:30:00.000Z")
  });
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
      hard_block_limit_usd: 500,
      daily_limit_usd: 1000
    },
    expires_at: "2026-06-30T23:59:59.000Z",
    signed_by: user.email
  });

  const checked = guard.checkPayment({
    ...request({
      idempotency_key: "idem_ttl",
      decision_ttl: "PT10M"
    }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });
  guard.now = () => new Date("2026-05-17T04:41:00.000Z");
  assert.throws(
    () => guard.executeMockPayment(checked.payment_request.id),
    /ttl expired/
  );
});

test("blocks agent from using another agent's mandate", () => {
  const { guard, mandate } = setup();

  const principalB = guard.createPrincipal({
    type: "company",
    legal_name: "XYZ Trading Limited",
    jurisdiction: "HK"
  });

  guard.createUser({
    principal_id: principalB.id,
    email: "finance@xyz.example",
    role: "finance_approver"
  });

  const agentB = guard.createAgent({
    principal_id: principalB.id,
    name: "OtherBot",
    type: "autonomous_api_buyer",
    wallet_address: "0xbbb0000000000000000000000000000000000001",
    chain: "base"
  });

  assert.throws(
    () =>
      guard.checkPayment({
        ...request({ idempotency_key: "idem_cross_agent" }),
        agent_id: agentB.id,
        mandate_id: mandate.id
      }),
    /mandate does not belong to agent/
  );
});

test("cannot create mandate for agent under a different principal", () => {
  const { guard, agent } = setup();

  const principalB = guard.createPrincipal({
    type: "company",
    legal_name: "XYZ Trading Limited",
    jurisdiction: "HK"
  });

  guard.createUser({
    principal_id: principalB.id,
    email: "finance@xyz.example",
    role: "finance_approver"
  });

  assert.throws(
    () =>
      guard.createMandate({
        agent_id: agent.id,
        principal_id: principalB.id,
        allowed_actions: ["buy_api_credits"],
        allowed_merchants: ["api.vendor.com"],
        allowed_tokens: ["USDC"],
        allowed_chains: ["base"],
        limits: {
          auto_approve_limit_usd: 20,
          human_approval_limit_usd: 100,
          hard_block_limit_usd: 500,
          daily_limit_usd: 1000
        },
        expires_at: "2026-06-30T23:59:59.000Z",
        signed_by: "finance@xyz.example"
      }),
    /agent does not belong to principal/
  );
});

test("cannot create mandate when signed_by user is missing for principal", () => {
  const { guard, agent, principal } = setup();

  assert.throws(
    () =>
      guard.createMandate({
        agent_id: agent.id,
        principal_id: principal.id,
        allowed_actions: ["buy_api_credits"],
        allowed_merchants: ["api.vendor.com"],
        allowed_tokens: ["USDC"],
        allowed_chains: ["base"],
        limits: {
          auto_approve_limit_usd: 20,
          human_approval_limit_usd: 100,
          hard_block_limit_usd: 500,
          daily_limit_usd: 1000
        },
        expires_at: "2026-06-30T23:59:59.000Z",
        signed_by: "unknown@example.com"
      }),
    /signed_by user not found for principal/
  );
});

test("rejects idempotency key reused across different mandates", () => {
  const { guard, agent, principal, user, mandate } = setup();
  const mandate2 = guard.createMandate({
    agent_id: agent.id,
    principal_id: principal.id,
    allowed_actions: ["buy_api_credits"],
    allowed_merchants: ["api.vendor.com"],
    allowed_tokens: ["USDC"],
    allowed_chains: ["base"],
    limits: {
      auto_approve_limit_usd: 50,
      human_approval_limit_usd: 200,
      hard_block_limit_usd: 500,
      daily_limit_usd: 1000
    },
    expires_at: "2026-06-30T23:59:59.000Z",
    signed_by: user.email
  });

  guard.checkPayment({
    ...request({ idempotency_key: "idem_mandate_hash" }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });

  assert.throws(
    () =>
      guard.checkPayment({
        ...request({ idempotency_key: "idem_mandate_hash" }),
        agent_id: agent.id,
        mandate_id: mandate2.id
      }),
    /idempotency_key was reused/
  );
});

test("evidence pack includes approver user and authority chain", () => {
  const { guard, agent, user, mandate } = setup();

  const checked = guard.checkPayment({
    ...request({ idempotency_key: "idem_evidence_approver" }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });

  const executed = guard.executeMockPayment(checked.payment_request.id);
  const pack = guard.exportEvidencePack(checked.payment_request.id);

  assert.equal(pack.approver_user.id, user.id);
  assert.equal(pack.approver_user.email, user.email);
  assert.equal(pack.approver_user.role, "finance_approver");

  assert.equal(pack.authority_chain_summary.approver_user_id, user.id);
  assert.equal(pack.authority_chain_summary.agent_id, agent.id);
  assert.equal(pack.authority_chain_summary.mandate_id, mandate.id);
  assert.equal(pack.authority_chain_summary.receipt_id, executed.receipt.id);

  assert.ok(
    pack.scoped_audit_events.some(
      (event) => event.type === "USER_CREATED" && event.subject_id === user.id
    )
  );
});

test("audit chain detects tampering", () => {
  const { guard, agent, mandate } = setup();
  const checked = guard.checkPayment({ ...request(), agent_id: agent.id, mandate_id: mandate.id });
  guard.executeMockPayment(checked.payment_request.id);
  assert.equal(guard.verifyAuditEvents().valid, true);

  const tampered = guard.store.auditEvents.map((event) => ({ ...event }));
  tampered[1].output_hash = "sha256:tampered";
  assert.equal(guard.verifyAuditEvents(tampered).valid, false);
});

test("composite screening blocks OFAC demo merchants", () => {
  const guard = new AgentPayGuard({ now: () => new Date("2026-05-17T04:30:00.000Z") });
  const principal = guard.createPrincipal({
    type: "company",
    legal_name: "OFAC Demo Co",
    jurisdiction: "HK"
  });
  const user = guard.createUser({
    principal_id: principal.id,
    email: "compliance@example.com",
    role: "finance_approver"
  });
  const agent = guard.createAgent({
    principal_id: principal.id,
    name: "OfacBot",
    type: "autonomous_api_buyer",
    wallet_address: "0xabc0000000000000000000000000000000000009",
    chain: "base"
  });
  const mandate = guard.createMandate({
    agent_id: agent.id,
    principal_id: principal.id,
    allowed_actions: ["buy_api_credits"],
    allowed_merchants: ["sanctioned-example.test"],
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

  const checked = guard.checkPayment({
    ...request({
      merchant: "sanctioned-example.test",
      idempotency_key: "idem_ofac_demo",
      merchant_request_id: "ofac_demo_vendor",
      nonce: "ofac_demo_nonce"
    }),
    agent_id: agent.id,
    mandate_id: mandate.id
  });

  assert.equal(checked.decision.status, "blocked");
  assert.equal(checked.decision.reason, "screening_hit");
  assert.match(checked.decision.screening_provider, /ofac_demo_v0\.2/);
  assert.ok(
    checked.decision.screening_result.checks.some(
      (check) => check.source === "ofac_demo_list" && check.status === "flagged"
    )
  );
});

test("sqlite store persists entities and audit events across restarts", () => {
  const dir = mkdtempSync(join(tmpdir(), "agentpay-sqlite-"));
  const dbPath = join(dir, "agentpay-test.db");

  try {
    const store1 = createStore({ kind: "sqlite", path: dbPath });
    const guard1 = new AgentPayGuard({
      store: store1,
      now: () => new Date("2026-05-17T04:30:00.000Z")
    });
    const principal = guard1.createPrincipal({
      type: "company",
      legal_name: "SQLite Persistence Co",
      jurisdiction: "HK"
    });
    const user = guard1.createUser({
      principal_id: principal.id,
      email: "ops@sqlite.example",
      role: "finance_approver"
    });
    const agent = guard1.createAgent({
      principal_id: principal.id,
      name: "SqliteBot",
      type: "autonomous_api_buyer",
      wallet_address: "0xabc0000000000000000000000000000000000008",
      chain: "base"
    });
    const mandate = guard1.createMandate({
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
    guard1.checkPayment({
      ...request({
        idempotency_key: "idem_sqlite_persist",
        merchant_request_id: "sqlite_vendor_1",
        nonce: "sqlite_nonce_1"
      }),
      agent_id: agent.id,
      mandate_id: mandate.id
    });

    const store2 = createStore({ kind: "sqlite", path: dbPath });
    const guard2 = new AgentPayGuard({ store: store2 });

    assert.equal(guard2.store.kind, "sqlite");
    assert.equal(guard2.store.principals.get(principal.id).legal_name, "SQLite Persistence Co");
    assert.ok(guard2.store.auditEvents.length >= 1);
    assert.equal(guard2.verifyAuditEvents().valid, true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
