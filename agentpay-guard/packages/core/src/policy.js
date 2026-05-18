import { ensurePositiveAmount, normalizeDomain } from "../../shared/src/schemas.js";

const POLICY_VERSION = "agentpay-policy-v0.1";

function includesNormalized(list = [], value) {
  return list.map(normalizeDomain).includes(normalizeDomain(value));
}

function walletMatches(list = [], value) {
  if (!value) return false;
  return list.map((item) => String(item).toLowerCase()).includes(String(value).toLowerCase());
}

export function evaluatePaymentPolicy({
  mandate,
  paymentRequest,
  now = new Date(),
  approvedDailyTotalUsd = 0
}) {
  const amount = ensurePositiveAmount(paymentRequest.amount_usd);
  const limits = mandate.limits ?? {};
  const rules_checked = [];
  const rules_triggered = [];

  const trigger = (id, action, reason) => {
    rules_checked.push(id);
    rules_triggered.push({ id, action, reason });
  };

  const check = (id) => rules_checked.push(id);

  if (mandate.status !== "active") {
    trigger("block_inactive_or_revoked_mandate", "block", "mandate_not_active");
  } else {
    check("block_inactive_or_revoked_mandate");
  }

  if (mandate.expires_at && new Date(mandate.expires_at).getTime() < now.getTime()) {
    trigger("block_expired_mandate", "block", "mandate_expired");
  } else {
    check("block_expired_mandate");
  }

  if (!includesNormalized(mandate.allowed_merchants, paymentRequest.merchant)) {
    trigger("block_disallowed_merchant", "block", "merchant_not_allowlisted");
  } else {
    check("block_disallowed_merchant");
  }

  if (!mandate.allowed_actions?.includes(paymentRequest.purpose)) {
    trigger("block_disallowed_action", "block", "purpose_not_allowed");
  } else {
    check("block_disallowed_action");
  }

  if (includesNormalized(mandate.denied_merchants, paymentRequest.merchant)) {
    trigger("block_denylisted_merchant", "block", "merchant_denylisted");
  } else {
    check("block_denylisted_merchant");
  }

  if (!mandate.allowed_tokens?.includes(paymentRequest.token)) {
    trigger("block_disallowed_token", "block", "token_not_allowed");
  } else {
    check("block_disallowed_token");
  }

  if (!mandate.allowed_chains?.includes(paymentRequest.chain)) {
    trigger("block_disallowed_chain", "block", "chain_not_allowed");
  } else {
    check("block_disallowed_chain");
  }

  if (walletMatches(mandate.denied_wallets, paymentRequest.counterparty_wallet_address)) {
    trigger("block_denylisted_wallet", "block", "wallet_denylisted");
  } else {
    check("block_denylisted_wallet");
  }

  if (limits.daily_limit_usd && approvedDailyTotalUsd + amount > Number(limits.daily_limit_usd)) {
    trigger("block_daily_limit_exceeded", "block", "daily_limit_exceeded");
  } else {
    check("block_daily_limit_exceeded");
  }

  if (amount > Number(limits.hard_block_limit_usd)) {
    trigger("block_hard_limit_exceeded", "block", "hard_block_limit_exceeded");
  } else {
    check("block_hard_limit_exceeded");
  }

  if (rules_triggered.some((rule) => rule.action === "block")) {
    const reasonPriority = [
      "wallet_denylisted",
      "merchant_denylisted",
      "mandate_not_active",
      "mandate_expired",
      "hard_block_limit_exceeded",
      "daily_limit_exceeded",
      "purpose_not_allowed",
      "merchant_not_allowlisted",
      "token_not_allowed",
      "chain_not_allowed"
    ];
    const primaryRule =
      reasonPriority
        .map((reason) => rules_triggered.find((rule) => rule.reason === reason))
        .find(Boolean) ?? rules_triggered.find((rule) => rule.action === "block");

    return {
      status: "blocked",
      reason: primaryRule.reason,
      approval_required: false,
      policy_version: POLICY_VERSION,
      rules_checked,
      rules_triggered
    };
  }

  check("apply_approval_thresholds");
  if (amount <= Number(limits.auto_approve_limit_usd)) {
    return {
      status: "approved",
      reason: "within_mandate",
      approval_required: false,
      policy_version: POLICY_VERSION,
      rules_checked,
      rules_triggered
    };
  }

  if (amount <= Number(limits.human_approval_limit_usd)) {
    return {
      status: "pending_human_approval",
      reason: "amount_exceeds_auto_limit",
      approval_required: true,
      policy_version: POLICY_VERSION,
      rules_checked,
      rules_triggered
    };
  }

  return {
    status: "manual_review",
    reason: "amount_between_human_and_hard_limit",
    approval_required: true,
    policy_version: POLICY_VERSION,
    rules_checked,
    rules_triggered
  };
}
