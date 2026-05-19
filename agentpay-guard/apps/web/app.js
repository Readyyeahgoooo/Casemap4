const state = {
  scenarios: [],
  previews: new Map(),
  activeScenario: null,
  activeTab: "summary",
  data: null
};

const statusClasses = {
  approved: "approved",
  pending_human_approval: "pending",
  manual_review: "pending",
  blocked: "blocked"
};

const statusLabels = {
  approved: "Approved",
  pending_human_approval: "Pending Human Approval",
  manual_review: "Manual Review",
  blocked: "Blocked"
};

const scenarioNumbers = {
  approved: "1",
  blocked: "2",
  "human-approval": "3"
};

const tabOrder = [
  ["summary", "Summary"],
  ["mandate", "Mandate"],
  ["decision", "Decision"],
  ["receipt", "Receipt"],
  ["case", "Case"],
  ["audit", "Audit Events"],
  ["full", "Full Evidence Pack"]
];

const ruleLabels = {
  authority_mandate_agent_binding: "Mandate belongs to this agent",
  authority_approver_principal_binding: "Approver belongs to this principal",
  block_inactive_or_revoked_mandate: "Mandate active",
  block_expired_mandate: "Mandate not expired",
  block_disallowed_merchant: "Merchant allowlisted",
  block_disallowed_action: "Purpose allowed",
  block_denylisted_merchant: "Merchant not denylisted",
  block_disallowed_token: "Token allowed",
  block_disallowed_chain: "Chain allowed",
  block_denylisted_wallet: "Wallet not denylisted",
  block_screening_result: "Screening clear",
  block_daily_limit_exceeded: "Daily limit not exceeded",
  block_hard_limit_exceeded: "Hard block limit not exceeded",
  apply_approval_thresholds: "Approval threshold applied",
  audit_chain_valid: "Audit chain valid",
  mandate_signature_valid: "Mandate signature valid",
  mandate_hash_matches: "Mandate hash matches decision-time snapshot"
};

const chainLabels = {
  principal: "Principal",
  approver: "Approver",
  agent: "Agent",
  mandate: "Mandate",
  request: "Payment Request",
  decision: "Decision",
  receipt: "Receipt",
  case: "Case"
};

function el(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function json(value) {
  return JSON.stringify(value, null, 2);
}

function shortHash(value) {
  if (!value) return "n/a";
  return `${String(value).slice(0, 14)}...${String(value).slice(-6)}`;
}

function formatTime(value) {
  if (!value) return "n/a";
  return new Date(value).toLocaleString("en-HK", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function capitalizeWords(value) {
  return String(value ?? "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function statusTone(status) {
  return statusClasses[status] ?? "pending";
}

function markerForStatus(status) {
  if (status === "approved") return "✓";
  if (status === "blocked") return "×";
  return "!";
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Request failed: ${path}`);
  return response.json();
}

async function loadScenarios() {
  const payload = await fetchJson("/demo/scenarios");
  state.scenarios = payload.scenarios;
  await Promise.all(
    state.scenarios.map(async (scenario) => {
      const preview = await fetchJson(`/demo/run/${scenario.id}`);
      state.previews.set(scenario.id, preview);
    })
  );
  renderScenarioButtons();
  renderScenarioRail();
  if (state.scenarios.length) {
    await runScenario(state.scenarios[0].id);
  }
}

async function runScenario(id) {
  state.activeScenario = id;
  state.data = state.previews.get(id) ?? (await fetchJson(`/demo/run/${id}`));
  state.activeTab = "summary";
  renderAll();
}

function renderScenarioButtons() {
  el("scenario-buttons").innerHTML = state.scenarios
    .map((scenario) => {
      const preview = state.previews.get(scenario.id);
      const status = preview?.evidence_pack?.decision?.status ?? scenario.emphasis;
      const tone = statusTone(status);
      const amount = preview?.evidence_pack?.payment_request?.amount_usd ?? "--";
      return `
        <button class="scenario-action ${tone} ${state.activeScenario === scenario.id ? "active" : ""}" data-scenario="${escapeHtml(scenario.id)}">
          <span class="action-icon">${markerForStatus(status)}</span>
          <span>
            <strong>${escapeHtml(scenario.label)}</strong>
            <small>${escapeHtml(amount)} USDC evidence path</small>
          </span>
        </button>
      `;
    })
    .join("");

  for (const button of document.querySelectorAll(".scenario-action")) {
    button.addEventListener("click", () => runScenario(button.dataset.scenario));
  }
}

function renderScenarioRail() {
  el("scenario-rail").innerHTML = state.scenarios
    .map((scenario) => {
      const preview = state.previews.get(scenario.id);
      if (!preview) return "";
      const pack = preview.evidence_pack;
      const decision = pack.decision;
      const tone = statusTone(decision.status);
      const failed = pack.decision.rules_triggered ?? [];
      const caseLabel = pack.case ? `${pack.case.id} · ${pack.case.status}` : pack.receipt?.id ?? "No case";
      return `
        <article class="scenario-card ${tone} ${state.activeScenario === scenario.id ? "active" : ""}" data-scenario="${escapeHtml(scenario.id)}">
          <button class="scenario-card-button" type="button" data-scenario="${escapeHtml(scenario.id)}">
            <span class="scenario-title">${scenarioNumbers[scenario.id]}. ${escapeHtml(scenario.title)}</span>
            <span class="scenario-status">${escapeHtml(statusLabels[decision.status] ?? decision.status)}</span>
          </button>
          <div class="scenario-card-grid">
            <div>
              <span>Reason</span>
              <strong>${escapeHtml(decision.reason)}</strong>
            </div>
            <div>
              <span>Amount</span>
              <strong>${escapeHtml(pack.payment_request.amount_usd)} ${escapeHtml(pack.payment_request.token)}</strong>
            </div>
            <div>
              <span>Merchant</span>
              <strong>${escapeHtml(pack.payment_request.merchant)}</strong>
            </div>
            <div>
              <span>Evidence</span>
              <strong>${escapeHtml(caseLabel)}</strong>
            </div>
          </div>
          <div class="mini-chain">${renderMiniChain(pack)}</div>
          <div class="mini-rules">
            ${failed.length ? failed.slice(0, 2).map((rule) => `<span class="fail">× ${escapeHtml(rule.reason)}</span>`).join("") : "<span class=\"pass\">✓ All policy checks passed</span>"}
            <span class="pass">✓ Audit chain valid</span>
          </div>
        </article>
      `;
    })
    .join("");

  for (const button of document.querySelectorAll(".scenario-card-button")) {
    button.addEventListener("click", () => runScenario(button.dataset.scenario));
  }
}

function renderMiniChain(pack) {
  const finalStatus = pack.receipt ? "receipt" : "case";
  return ["principal", "approver", "agent", "mandate", "request", "decision", finalStatus]
    .map((item) => `<span title="${escapeHtml(chainLabels[item])}">${item[0].toUpperCase()}</span>`)
    .join("<b>→</b>");
}

function renderDecisionSummary(data) {
  const pack = data.evidence_pack;
  const decision = pack.decision ?? {};
  const receipt = pack.receipt;
  const reviewCase = pack.case;
  const tone = statusTone(decision.status);

  el("decision-summary").innerHTML = `
    <div class="verdict-strip ${tone}">
      <div>
        <span class="verdict-label">Decision</span>
        <strong>${escapeHtml(statusLabels[decision.status] ?? capitalizeWords(decision.status))}</strong>
        <span>Reason: ${escapeHtml(decision.reason ?? "n/a")}</span>
      </div>
      <div>
        <span class="verdict-label">Amount</span>
        <strong>${escapeHtml(pack.payment_request.amount_usd)} ${escapeHtml(pack.payment_request.token)}</strong>
        <span>To ${escapeHtml(pack.payment_request.merchant)}</span>
      </div>
      <div>
        <span class="verdict-label">Audit Chain</span>
        <strong>${pack.audit_verification.valid ? "Valid" : "Invalid"}</strong>
        <span>${escapeHtml(pack.decision.policy_version)}</span>
      </div>
    </div>

    <div class="case-columns">
      ${renderCaseColumn("Payment Request", [
        ["Purpose", pack.payment_request.purpose],
        ["Merchant", pack.payment_request.merchant],
        ["Hash", shortHash(pack.payment_request.payment_request_hash)]
      ])}
      ${renderCaseColumn("Agent", [
        ["Name", pack.agent.name],
        ["Wallet", shortHash(pack.agent.wallet_address)],
        ["Chain", pack.agent.chain]
      ])}
      ${renderCaseColumn("Mandate", [
        ["Mandate ID", pack.mandate.id],
        ["Signer", pack.approver_user?.email ?? "n/a"],
        ["Status", pack.mandate.status]
      ])}
      ${renderCaseColumn("Outcome", [
        ["Decision ID", decision.id],
        [receipt ? "Receipt ID" : "Case ID", receipt?.id ?? reviewCase?.id ?? "n/a"],
        [receipt ? "Mock Tx" : "Review", receipt ? shortHash(receipt.tx_hash) : reviewCase?.status ?? "n/a"]
      ])}
    </div>
  `;
}

function renderCaseColumn(title, rows) {
  return `
    <div class="case-column">
      <h3>${escapeHtml(title)}</h3>
      ${rows
        .map(
          ([label, value]) => `
            <dl>
              <dt>${escapeHtml(label)}</dt>
              <dd>${escapeHtml(value)}</dd>
            </dl>
          `
        )
        .join("")}
    </div>
  `;
}

function renderAuthorityChain(data) {
  const pack = data.evidence_pack;
  const decision = pack.decision ?? {};
  const finalItem = pack.receipt
    ? ["receipt", pack.receipt.id, "Receipt generated"]
    : ["case", pack.case?.id ?? "No case", pack.case?.status ?? "Awaiting review"];
  const chain = [
    ["principal", pack.principal.legal_name, `${pack.principal.jurisdiction} company`],
    ["approver", pack.approver_user?.email ?? "n/a", capitalizeWords(pack.approver_user?.role ?? "unknown")],
    ["agent", pack.agent.name, pack.agent.id],
    ["mandate", pack.mandate.id, pack.mandate.status],
    ["request", pack.payment_request.id, `${pack.payment_request.amount_usd} ${pack.payment_request.token}`],
    ["decision", statusLabels[decision.status] ?? decision.status, decision.reason],
    finalItem
  ];

  el("authority-chain").innerHTML = chain
    .map(
      ([kind, title, detail], index) => `
        <div class="chain-node ${kind} ${kind === "decision" ? statusTone(decision.status) : ""}">
          <span class="node-icon">${kind[0].toUpperCase()}</span>
          <strong>${escapeHtml(title)}</strong>
          <small>${escapeHtml(detail)}</small>
        </div>
        ${index < chain.length - 1 ? "<span class=\"chain-arrow\">→</span>" : ""}
      `
    )
    .join("");
}

function buildRules(pack) {
  const decision = pack.decision ?? {};
  const triggered = new Map((decision.rules_triggered ?? []).map((rule) => [rule.id, rule]));
  const authorityRules = [
    {
      id: "authority_mandate_agent_binding",
      passed: pack.mandate.agent_id === pack.agent.id && pack.mandate.principal_id === pack.principal.id,
      reason: "Mandate agent/principal binding"
    },
    {
      id: "authority_approver_principal_binding",
      passed: pack.approver_user?.principal_id === pack.principal.id,
      reason: "Mandate signer is an active principal user"
    }
  ];
  const policyRules = (decision.rules_checked ?? []).map((ruleId) => {
    const hit = triggered.get(ruleId);
    return {
      id: ruleId,
      passed: !hit,
      reason: hit ? hit.reason : "Passed"
    };
  });
  const auditRule = {
    id: "audit_chain_valid",
    passed: pack.audit_verification.valid,
    reason: pack.audit_verification.valid ? "Passed" : "Audit verification failed"
  };
  const signatureRule = {
    id: "mandate_signature_valid",
    passed: pack.mandate_integrity?.mandate_signature_valid === true,
    reason: pack.mandate_integrity?.mandate_signature_valid ? "Ed25519 mandate signature valid" : "Mandate signature invalid"
  };
  const mandateHashRule = {
    id: "mandate_hash_matches",
    passed: pack.mandate_integrity?.mandate_hash_matches === true,
    reason: pack.mandate_integrity?.mandate_hash_matches ? "Mandate hash unchanged since decision" : "Mandate hash drift detected"
  };
  return [...authorityRules, signatureRule, mandateHashRule, ...policyRules, auditRule];
}

function renderRuleChecklist(data) {
  const rules = buildRules(data.evidence_pack);
  el("rule-checklist").innerHTML = rules
    .map((rule) => {
      const tone = rule.passed ? "good" : "bad";
      const marker = rule.passed ? "✓" : "×";
      const label = ruleLabels[rule.id] ?? capitalizeWords(rule.id);
      return `
        <div class="rule-item ${tone}">
          <span>${marker}</span>
          <strong>${escapeHtml(label)}</strong>
          <small>${escapeHtml(rule.reason)}</small>
        </div>
      `;
    })
    .join("");
}

function renderTimeline(data) {
  el("audit-timeline").innerHTML = data.evidence_pack.scoped_audit_events
    .map(
      (event) => `
        <div class="timeline-item">
          <span class="timeline-dot"></span>
          <div>
            <strong>${escapeHtml(capitalizeWords(event.type))}</strong>
            <small>${escapeHtml(formatTime(event.created_at))}</small>
          </div>
          <code>${escapeHtml(shortHash(event.event_hash))}</code>
        </div>
      `
    )
    .join("");
}

function renderAuditVerification(data, verification = data.evidence_pack.audit_verification) {
  const pack = data.evidence_pack;
  const first = pack.scoped_audit_events[0];
  const last = pack.scoped_audit_events.at(-1);
  const checkpoint = pack.audit_checkpoint;
  el("audit-verification").innerHTML = `
    <div class="verification-card ${verification.valid ? "approved" : "blocked"}">
      <span class="verification-mark">${verification.valid ? "✓" : "×"}</span>
      <div>
        <strong>${verification.valid ? "Valid" : "Invalid"}</strong>
        <small>Audit chain is hash-linked and tamper-evident.</small>
      </div>
    </div>
    <dl class="verification-list">
      <div><dt>Scoped Events</dt><dd>${pack.scoped_audit_events.length}</dd></div>
      <div><dt>Total Events</dt><dd>${pack.audit_events.length}</dd></div>
      <div><dt>Store</dt><dd>${escapeHtml(pack.store?.kind ?? "memory")}</dd></div>
      <div><dt>First Hash</dt><dd>${escapeHtml(shortHash(first?.event_hash))}</dd></div>
      <div><dt>Latest Hash</dt><dd>${escapeHtml(shortHash(last?.event_hash))}</dd></div>
      <div><dt>Checkpoint</dt><dd>${checkpoint ? escapeHtml(shortHash(checkpoint.root_hash)) : "Not anchored yet"}</dd></div>
    </dl>
  `;
}

async function verifyAuditChainFromApi() {
  if (!state.data?.evidence_pack?.payment_request?.id) return;
  const subjectId = state.data.evidence_pack.payment_request.id;
  const result = await fetchJson(`/audit-events/verify?subject_id=${encodeURIComponent(subjectId)}`);
  renderAuditVerification(state.data, result.verification);
}

function renderTabs(data) {
  const pack = data.evidence_pack;
  const values = {
    summary: {
      scenario: data.scenario,
      decision: pack.decision,
      audit_verification: pack.audit_verification,
      authority_chain_summary: pack.authority_chain_summary
    },
    mandate: pack.mandate,
    decision: pack.decision,
    receipt: pack.receipt ?? { note: "No receipt was generated because execution did not occur." },
    case: pack.case ?? { note: "No review case was opened for this request." },
    audit: pack.scoped_audit_events,
    full: pack
  };

  el("raw-tabs").innerHTML = tabOrder
    .map(
      ([key, label]) => `
        <button class="tab-button ${state.activeTab === key ? "active" : ""}" data-tab="${key}">${escapeHtml(label)}</button>
      `
    )
    .join("");

  for (const button of document.querySelectorAll(".tab-button")) {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      renderTabs(data);
    });
  }

  el("raw-json").textContent = json(values[state.activeTab]);
}

function bindStaticActions() {
  for (const button of document.querySelectorAll("[data-tab-jump]")) {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tabJump;
      renderTabs(state.data);
      el("raw-evidence").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  const verifyButton = el("verify-chain-button");
  if (verifyButton) {
    verifyButton.addEventListener("click", () => {
      verifyAuditChainFromApi().catch((error) => {
        console.error(error);
        el("audit-verification").innerHTML = `<div class="empty-state">Audit verification request failed.</div>`;
      });
    });
  }
}

function renderAll() {
  if (!state.data) return;
  renderScenarioButtons();
  renderScenarioRail();
  renderDecisionSummary(state.data);
  renderAuthorityChain(state.data);
  renderRuleChecklist(state.data);
  renderTimeline(state.data);
  renderAuditVerification(state.data);
  renderTabs(state.data);
}

bindStaticActions();
loadScenarios().catch((error) => {
  console.error(error);
  el("decision-summary").innerHTML = `<div class="empty-state">Failed to load demo data.</div>`;
});
