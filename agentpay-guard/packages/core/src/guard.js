import {
  ConflictError,
  ensureRole,
  normalizeDomain,
  normalizeWallet,
  requireFields,
  ValidationError
} from "../../shared/src/schemas.js";
import { paymentRequestHash } from "../../shared/src/hash.js";
import { normalizeDecisionTtl, parseIsoDurationMs } from "../../shared/src/duration.js";
import {
  generateSigningKeyPair,
  mandateHash,
  MANDATE_SIGNATURE_TYPE,
  signMandateHash,
  verifyMandateSignature
} from "../../shared/src/mandate-sign.js";
import { createAuditEvent, verifyAuditChain } from "./audit.js";
import { evaluatePaymentPolicy } from "./policy.js";
import { publicUser, redactSensitive } from "./redact.js";
import { createCompositeScreeningProvider } from "./screening.js";
import { maybeAppendAuditCheckpoint, readLatestAuditCheckpoint } from "./checkpoint.js";
import { createStore } from "./store-factory.js";

const DEFAULT_ROLES = ["admin", "developer", "compliance_reviewer", "finance_approver", "read_only_auditor"];
const EVM_CHAINS = new Set(["base", "ethereum", "mainnet", "sepolia", "polygon"]);

function merchantRequestIndexKey(agentId, merchant, merchantRequestId) {
  return `${agentId}|${merchant}|${merchantRequestId}`;
}

function nonceIndexKey(agentId, nonce) {
  return `${agentId}|${nonce}`;
}

function scopeAuditEventsForEvidencePack(events, relatedIds) {
  return events.filter(
    (event) =>
      relatedIds.has(event.subject_id) || (event.case_id !== null && relatedIds.has(event.case_id))
  );
}

export class AgentPayGuard {
  constructor({
    store = createStore(),
    now = () => new Date(),
    screeningProvider = createCompositeScreeningProvider()
  } = {}) {
    this.store = store;
    this.now = now;
    this.screeningProvider = screeningProvider;
  }

  appendAuditEvent(input) {
    const id = this.store.nextId("evt");
    const previous = this.store.auditEvents.at(-1)?.event_hash ?? null;
    const event = createAuditEvent({
      id,
      previous_event_hash: previous,
      created_at: this.now().toISOString(),
      ...input,
      input: redactSensitive(input.input ?? {}),
      output: redactSensitive(input.output ?? {})
    });
    this.store.auditEvents.push(event);
    maybeAppendAuditCheckpoint(this.store.auditEvents, { now: this.now });
    return event;
  }

  createPrincipal(input, actor = "system") {
    requireFields(input, ["type", "legal_name", "jurisdiction"], "principal");
    const principal = {
      id: input.id ?? this.store.nextId("prn"),
      type: input.type,
      legal_name: input.legal_name,
      jurisdiction: input.jurisdiction,
      company_number: input.company_number ?? null,
      status: input.status ?? "active",
      created_at: this.now().toISOString()
    };
    this.store.principals.set(principal.id, principal);
    this.appendAuditEvent({ type: "PRINCIPAL_CREATED", actor, subject_id: principal.id, input, output: principal });
    return principal;
  }

  createUser(input, actor = "system") {
    requireFields(input, ["principal_id", "email", "role"], "user");
    ensureRole(input.role);
    this.requirePrincipal(input.principal_id);

    let signing_public_key = input.signing_public_key ?? null;
    let signing_private_key = input.signing_private_key ?? null;
    if (!signing_public_key && input.role === "finance_approver") {
      const keys = generateSigningKeyPair();
      signing_public_key = keys.publicKey;
      signing_private_key = keys.privateKey;
    }

    const user = {
      id: input.id ?? this.store.nextId("usr"),
      principal_id: input.principal_id,
      email: input.email,
      role: input.role,
      status: input.status ?? "active",
      signing_public_key,
      signing_private_key,
      created_at: this.now().toISOString()
    };
    this.store.users.set(user.id, user);
    this.appendAuditEvent({ type: "USER_CREATED", actor, subject_id: user.id, input, output: publicUser(user) });
    return publicUser(user);
  }

  createAgent(input, actor = "system") {
    requireFields(input, ["principal_id", "name", "type", "wallet_address", "chain"], "agent");
    this.requirePrincipal(input.principal_id);
    const chain = String(input.chain).toLowerCase();
    const wallet_address = EVM_CHAINS.has(chain)
      ? normalizeWallet(input.wallet_address)
      : String(input.wallet_address).trim();

    const agent = {
      id: input.id ?? this.store.nextId("agt"),
      principal_id: input.principal_id,
      name: input.name,
      type: input.type,
      wallet_address,
      chain,
      status: input.status ?? "active",
      created_at: this.now().toISOString()
    };
    this.store.agents.set(agent.id, agent);
    this.appendAuditEvent({ type: "AGENT_CREATED", actor, subject_id: agent.id, input, output: agent });
    return agent;
  }

  createMandate(input, actor = "system") {
    requireFields(input, ["agent_id", "principal_id", "allowed_actions", "allowed_merchants", "allowed_tokens", "allowed_chains", "limits", "expires_at", "signed_by"], "mandate");
    const agent = this.requireAgent(input.agent_id);
    const principal = this.requirePrincipal(input.principal_id);
    if (agent.principal_id !== principal.id) {
      throw new ConflictError("agent does not belong to principal", {
        agent_id: agent.id,
        agent_principal_id: agent.principal_id,
        principal_id: principal.id
      });
    }
    const signer = this.requireUserByEmailForPrincipal(input.signed_by, principal.id);
    if (!signer.signing_private_key || !signer.signing_public_key) {
      throw new ValidationError("signer must have a demo signing key to create mandates", {
        signer_user_id: signer.id,
        email: signer.email
      });
    }

    const mandateId = input.id ?? this.store.nextId("mnd");
    const mandateCore = {
      id: mandateId,
      agent_id: input.agent_id,
      principal_id: input.principal_id,
      signer_user_id: signer.id,
      allowed_actions: input.allowed_actions,
      allowed_merchants: input.allowed_merchants.map(normalizeDomain),
      denied_merchants: (input.denied_merchants ?? []).map(normalizeDomain),
      allowed_tokens: input.allowed_tokens,
      allowed_chains: input.allowed_chains,
      denied_wallets: (input.denied_wallets ?? []).map((wallet) => normalizeWallet(wallet)),
      limits: {
        auto_approve_limit_usd: Number(input.limits.auto_approve_limit_usd),
        human_approval_limit_usd: Number(input.limits.human_approval_limit_usd),
        hard_block_limit_usd: Number(input.limits.hard_block_limit_usd),
        daily_limit_usd: input.limits.daily_limit_usd === undefined ? null : Number(input.limits.daily_limit_usd)
      },
      status: input.status ?? "active",
      signed_by: input.signed_by,
      expires_at: input.expires_at,
      created_at: this.now().toISOString(),
      revoked_at: null
    };

    const hash = mandateHash(mandateCore);
    const signed_at = this.now().toISOString();
    const signature = signMandateHash(hash, signer.signing_private_key);
    const verification = verifyMandateSignature({
      ...mandateCore,
      mandate_hash: hash,
      signature_type: MANDATE_SIGNATURE_TYPE,
      signature,
      signed_at,
      signer_public_key: signer.signing_public_key
    });
    if (!verification.valid) {
      throw new ValidationError("mandate signature verification failed at creation", verification);
    }

    const mandate = {
      ...mandateCore,
      mandate_hash: hash,
      signature_type: MANDATE_SIGNATURE_TYPE,
      signature,
      signed_at,
      signer_public_key: signer.signing_public_key
    };
    this.store.mandates.set(mandate.id, mandate);
    this.appendAuditEvent({ type: "MANDATE_CREATED", actor, subject_id: mandate.id, input, output: mandate });
    return mandate;
  }

  revokeMandate(mandateId, actor = "system") {
    const mandate = this.requireMandate(mandateId);
    const updated = {
      ...mandate,
      status: "revoked",
      revoked_at: this.now().toISOString()
    };
    this.store.mandates.set(mandateId, updated);
    this.appendAuditEvent({ type: "MANDATE_REVOKED", actor, subject_id: mandateId, input: { mandate_id: mandateId }, output: updated });
    return updated;
  }

  checkPayment(input, actor = "system") {
    requireFields(input, ["agent_id", "merchant", "amount_usd", "token", "chain", "purpose", "idempotency_key"], "payment_request");

    const agent = this.requireAgent(input.agent_id);
    const principal = this.requirePrincipal(agent.principal_id);
    const mandate = input.mandate_id ? this.requireMandate(input.mandate_id) : this.findActiveMandateForAgent(agent.id);
    this.assertMandateBelongsToAgent(mandate, agent, principal);

    if (!input.merchant_request_id && !input.nonce) {
      throw new ValidationError("merchant_request_id or nonce is required for replay protection", {
        agent_id: agent.id
      });
    }

    const decisionTtl = normalizeDecisionTtl(input.decision_ttl);
    parseIsoDurationMs(decisionTtl);

    const merchant = normalizeDomain(input.merchant);
    const counterparty_wallet_address = input.counterparty_wallet_address
      ? normalizeWallet(input.counterparty_wallet_address)
      : null;

    const hashInput = {
      ...input,
      mandate_id: mandate.id,
      decision_ttl: decisionTtl,
      merchant,
      counterparty_wallet_address
    };
    const computedRequestHash = paymentRequestHash(hashInput);
    if (input.payment_request_hash && input.payment_request_hash !== computedRequestHash) {
      throw new ValidationError("payment_request_hash does not match request payload", {
        expected: computedRequestHash,
        actual: input.payment_request_hash
      });
    }
    const requestHash = input.payment_request_hash ?? computedRequestHash;
    const previous = this.store.idempotency.get(input.idempotency_key);

    if (previous) {
      if (previous.payment_request_hash !== requestHash) {
        throw new ConflictError("idempotency_key was reused with a different payment request", {
          idempotency_key: input.idempotency_key
        });
      }
      return {
        idempotent: true,
        payment_request: this.store.paymentRequests.get(previous.payment_request_id),
        decision: this.store.policyDecisions.get(previous.decision_id)
      };
    }

    this.assertReplayProtection({
      agentId: agent.id,
      merchant,
      merchantRequestId: input.merchant_request_id ?? null,
      nonce: input.nonce ?? null
    });

    const mandateHashAtDecision = mandateHash(mandate);
    const paymentRequest = {
      id: input.id ?? this.store.nextId("payreq"),
      agent_id: agent.id,
      mandate_id: mandate.id,
      merchant,
      amount_usd: String(input.amount_usd),
      token: input.token,
      chain: input.chain,
      purpose: input.purpose,
      counterparty_wallet_address,
      merchant_request_id: input.merchant_request_id ?? null,
      nonce: input.nonce ?? null,
      idempotency_key: input.idempotency_key,
      payment_request_hash: requestHash,
      decision_ttl: decisionTtl,
      status: "checked",
      created_at: this.now().toISOString()
    };
    this.store.paymentRequests.set(paymentRequest.id, paymentRequest);
    this.indexReplayIdentifiers(paymentRequest);

    const screeningResult = this.screeningProvider.screenPaymentRequest({
      principal,
      agent,
      mandate,
      paymentRequest
    });

    const policyResult = evaluatePaymentPolicy({
      mandate,
      paymentRequest,
      screeningResult,
      now: this.now(),
      approvedDailyTotalUsd: this.approvedDailyTotalUsd(agent.id)
    });
    const decision = {
      id: this.store.nextId("dec"),
      payment_request_id: paymentRequest.id,
      mandate_id: mandate.id,
      agent_id: agent.id,
      principal_id: principal.id,
      status: policyResult.status,
      reason: policyResult.reason,
      approval_required: policyResult.approval_required,
      rules_checked: policyResult.rules_checked,
      rules_triggered: policyResult.rules_triggered,
      policy_version: policyResult.policy_version,
      mandate_hash: mandateHashAtDecision,
      payment_request_hash: requestHash,
      screening_status: screeningResult.status,
      screening_provider: screeningResult.provider,
      screening_result: screeningResult,
      created_at: this.now().toISOString()
    };
    this.store.policyDecisions.set(decision.id, decision);
    this.store.idempotency.set(input.idempotency_key, {
      payment_request_hash: requestHash,
      payment_request_id: paymentRequest.id,
      decision_id: decision.id
    });

    let reviewCase = null;
    if (decision.status !== "approved") {
      reviewCase = this.createCaseForDecision(decision, actor);
    }

    this.appendAuditEvent({
      type: "POLICY_DECISION",
      actor,
      subject_id: paymentRequest.id,
      case_id: reviewCase?.id ?? null,
      input: { payment_request: paymentRequest, mandate, screening_result: screeningResult },
      output: decision,
      policy_version: decision.policy_version
    });

    return {
      idempotent: false,
      payment_request: paymentRequest,
      decision,
      case: reviewCase
    };
  }

  executeMockPayment(paymentRequestId, actor = "system") {
    const paymentRequest = this.requirePaymentRequest(paymentRequestId);
    const existingPayment = [...this.store.payments.values()].find(
      (item) => item.payment_request_id === paymentRequestId
    );
    if (existingPayment) {
      throw new ConflictError("mock payment already executed", {
        payment_request_id: paymentRequestId,
        payment_id: existingPayment.id
      });
    }

    const ttlMs = parseIsoDurationMs(paymentRequest.decision_ttl);
    const expiresAt = new Date(paymentRequest.created_at).getTime() + ttlMs;
    if (this.now().getTime() > expiresAt) {
      throw new ConflictError("payment decision ttl expired", {
        payment_request_id: paymentRequestId,
        created_at: paymentRequest.created_at,
        decision_ttl: paymentRequest.decision_ttl
      });
    }

    const decision = [...this.store.policyDecisions.values()].find(
      (item) => item.payment_request_id === paymentRequestId
    );
    if (!decision || decision.status !== "approved") {
      throw new ConflictError("mock payment can only execute after an approved decision", {
        payment_request_id: paymentRequestId,
        decision_status: decision?.status ?? null
      });
    }

    const executedAt = this.now().toISOString();
    const payment = {
      id: this.store.nextId("pay"),
      payment_request_id: paymentRequestId,
      decision_id: decision.id,
      tx_hash: `mock_tx_${paymentRequest.payment_request_hash.slice(-16)}`,
      chain: paymentRequest.chain,
      token: paymentRequest.token,
      amount_usd: paymentRequest.amount_usd,
      status: "executed",
      executed_at: executedAt
    };
    this.store.payments.set(payment.id, payment);
    this.store.paymentRequests.set(paymentRequestId, {
      ...paymentRequest,
      status: "executed",
      executed_at: executedAt
    });

    const receipt = this.generateReceipt(payment, paymentRequest, decision);
    this.store.receipts.set(receipt.id, receipt);

    this.appendAuditEvent({ type: "MOCK_PAYMENT_EXECUTED", actor, subject_id: paymentRequestId, input: { payment_request_id: paymentRequestId }, output: payment });
    this.appendAuditEvent({ type: "RECEIPT_GENERATED", actor, subject_id: paymentRequestId, input: payment, output: receipt });

    return { payment, receipt };
  }

  exportEvidencePack(paymentRequestId) {
    const paymentRequest = this.requirePaymentRequest(paymentRequestId);
    const mandate = this.requireMandate(paymentRequest.mandate_id);
    const agent = this.requireAgent(paymentRequest.agent_id);
    const principal = this.requirePrincipal(agent.principal_id);
    const decision = [...this.store.policyDecisions.values()].find((item) => item.payment_request_id === paymentRequestId) ?? null;
    const payment = [...this.store.payments.values()].find((item) => item.payment_request_id === paymentRequestId) ?? null;
    const receipt = payment ? [...this.store.receipts.values()].find((item) => item.payment_id === payment.id) ?? null : null;
    const reviewCase = decision ? [...this.store.cases.values()].find((item) => item.decision_id === decision.id) ?? null : null;
    const approverUser =
      mandate.signer_user_id
        ? this.store.users.get(mandate.signer_user_id) ?? null
        : this.findUserByEmailForPrincipal(mandate.signed_by, mandate.principal_id);
    const authority_chain_summary = {
      principal_id: principal.id,
      approver_user_id: approverUser?.id ?? null,
      agent_id: agent.id,
      mandate_id: mandate.id,
      payment_request_id: paymentRequest.id,
      decision_id: decision?.id ?? null,
      payment_id: payment?.id ?? null,
      receipt_id: receipt?.id ?? null,
      case_id: reviewCase?.id ?? null
    };
    const relatedIds = new Set(
      [
        principal.id,
        approverUser?.id,
        agent.id,
        mandate.id,
        paymentRequest.id,
        decision?.id,
        payment?.id,
        receipt?.id,
        reviewCase?.id
      ].filter(Boolean)
    );
    const scoped_audit_events = scopeAuditEventsForEvidencePack(this.store.auditEvents, relatedIds);
    const current_mandate_hash = mandateHash(mandate);
    const mandate_signature = verifyMandateSignature(mandate);
    const latest_checkpoint = readLatestAuditCheckpoint();

    return {
      evidence_pack_version: "agentpay-evidence-v0.1.2",
      exported_at: this.now().toISOString(),
      principal,
      approver_user: publicUser(approverUser),
      agent,
      mandate,
      payment_request: paymentRequest,
      decision,
      payment,
      receipt,
      case: reviewCase,
      authority_chain_summary,
      mandate_integrity: {
        mandate_hash_at_decision: decision?.mandate_hash ?? null,
        current_mandate_hash,
        mandate_hash_matches: decision?.mandate_hash === current_mandate_hash,
        mandate_signature_valid: mandate_signature.valid,
        mandate_signature_reason: mandate_signature.reason ?? null
      },
      audit_checkpoint: latest_checkpoint,
      store: {
        kind: this.store.kind ?? "memory",
        path: this.store.path ?? null
      },
      audit_events: this.store.auditEvents,
      scoped_audit_events,
      audit_verification: verifyAuditChain(this.store.auditEvents)
    };
  }

  verifyAuditEvents(events = this.store.auditEvents) {
    return verifyAuditChain(events);
  }

  getReceipt(receiptId) {
    return this.store.receipts.get(receiptId) ?? null;
  }

  roles() {
    return DEFAULT_ROLES;
  }

  createCaseForDecision(decision, actor) {
    const reviewCase = {
      id: this.store.nextId("case"),
      type: decision.status === "blocked" ? "blocked_payment_review" : "agent_payment_review",
      subject_id: decision.payment_request_id,
      decision_id: decision.id,
      status: decision.status === "blocked" ? "open" : "pending_review",
      risk_level: decision.status === "blocked" ? "high" : "medium",
      assigned_to: null,
      decision: decision.status,
      decision_reason: decision.reason,
      reviewer_notes: [],
      created_at: this.now().toISOString(),
      closed_at: null
    };
    this.store.cases.set(reviewCase.id, reviewCase);
    this.appendAuditEvent({ type: "CASE_OPENED", actor, subject_id: reviewCase.id, case_id: reviewCase.id, input: decision, output: reviewCase });
    return reviewCase;
  }

  generateReceipt(payment, paymentRequest, decision) {
    const agent = this.requireAgent(paymentRequest.agent_id);
    const principal = this.requirePrincipal(agent.principal_id);
    return {
      id: this.store.nextId("rcpt"),
      payment_id: payment.id,
      payment_request_id: paymentRequest.id,
      decision_id: decision.id,
      mandate_id: paymentRequest.mandate_id,
      agent_id: agent.id,
      principal: principal.legal_name,
      merchant: paymentRequest.merchant,
      purpose: paymentRequest.purpose,
      amount_usd: paymentRequest.amount_usd,
      token: paymentRequest.token,
      chain: paymentRequest.chain,
      tx_hash: payment.tx_hash,
      policy_decision: decision.status,
      screening_status: decision.screening_status,
      created_at: this.now().toISOString()
    };
  }

  approvedDailyTotalUsd(agentId) {
    const today = this.now().toISOString().slice(0, 10);
    let total = 0;
    for (const decision of this.store.policyDecisions.values()) {
      if (decision.agent_id !== agentId || decision.status !== "approved" || !decision.created_at.startsWith(today)) continue;
      const request = this.store.paymentRequests.get(decision.payment_request_id);
      total += Number(request?.amount_usd ?? 0);
    }
    return total;
  }

  findActiveMandateForAgent(agentId) {
    const mandate = [...this.store.mandates.values()].find((item) => item.agent_id === agentId && item.status === "active");
    if (!mandate) {
      throw new ConflictError("no active mandate found for agent", { agent_id: agentId });
    }
    return mandate;
  }

  requirePrincipal(id) {
    const principal = this.store.principals.get(id);
    if (!principal) throw new ConflictError("principal not found", { id });
    return principal;
  }

  requireAgent(id) {
    const agent = this.store.agents.get(id);
    if (!agent) throw new ConflictError("agent not found", { id });
    return agent;
  }

  requireMandate(id) {
    const mandate = this.store.mandates.get(id);
    if (!mandate) throw new ConflictError("mandate not found", { id });
    return mandate;
  }

  requirePaymentRequest(id) {
    const paymentRequest = this.store.paymentRequests.get(id);
    if (!paymentRequest) throw new ConflictError("payment request not found", { id });
    return paymentRequest;
  }

  assertMandateBelongsToAgent(mandate, agent, principal) {
    if (mandate.agent_id !== agent.id || mandate.principal_id !== principal.id) {
      throw new ConflictError("mandate does not belong to agent", {
        agent_id: agent.id,
        principal_id: principal.id,
        mandate_id: mandate.id,
        mandate_agent_id: mandate.agent_id,
        mandate_principal_id: mandate.principal_id
      });
    }
  }

  requireUserByEmailForPrincipal(email, principalId) {
    const user = this.findUserByEmailForPrincipal(email, principalId);
    if (!user) {
      throw new ConflictError("signed_by user not found for principal", {
        email,
        principal_id: principalId
      });
    }
    return user;
  }

  findUserByEmailForPrincipal(email, principalId) {
    return (
      [...this.store.users.values()].find(
        (item) =>
          item.email === email &&
          item.principal_id === principalId &&
          item.status === "active"
      ) ?? null
    );
  }

  assertReplayProtection({ agentId, merchant, merchantRequestId, nonce }) {
    if (merchantRequestId) {
      const key = merchantRequestIndexKey(agentId, merchant, merchantRequestId);
      if (this.store.merchantRequestIndex.has(key)) {
        throw new ConflictError("merchant_request_id was already used for this agent and merchant", {
          agent_id: agentId,
          merchant,
          merchant_request_id: merchantRequestId,
          existing_payment_request_id: this.store.merchantRequestIndex.get(key)
        });
      }
    }

    if (nonce) {
      const key = nonceIndexKey(agentId, nonce);
      if (this.store.nonceIndex.has(key)) {
        throw new ConflictError("nonce was already used for this agent", {
          agent_id: agentId,
          nonce,
          existing_payment_request_id: this.store.nonceIndex.get(key)
        });
      }
    }
  }

  indexReplayIdentifiers(paymentRequest) {
    if (paymentRequest.merchant_request_id) {
      this.store.merchantRequestIndex.set(
        merchantRequestIndexKey(paymentRequest.agent_id, paymentRequest.merchant, paymentRequest.merchant_request_id),
        paymentRequest.id
      );
    }
    if (paymentRequest.nonce) {
      this.store.nonceIndex.set(nonceIndexKey(paymentRequest.agent_id, paymentRequest.nonce), paymentRequest.id);
    }
  }
}
