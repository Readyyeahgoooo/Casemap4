import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { normalizeDomain, normalizeWallet } from "../../shared/src/schemas.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

function normalizeMerchantSet(values = []) {
  return new Set(values.map((value) => normalizeDomain(value)));
}

function normalizeWalletSet(values = []) {
  return new Set(values.map((value) => normalizeWallet(value)).filter(Boolean));
}

function buildScreeningResult({ provider, checks }) {
  const blocked = checks.some((check) => check.status === "flagged");
  return {
    provider,
    status: blocked ? "flagged" : "clear",
    blocked,
    reason: blocked ? "screening_hit" : "screening_clear",
    checks
  };
}

export function createDemoScreeningProvider({
  flaggedMerchants = [],
  flaggedWallets = []
} = {}) {
  const merchants = normalizeMerchantSet(flaggedMerchants);
  const wallets = normalizeWalletSet(flaggedWallets);

  return {
    id: "demo_screening_v0.2",
    screenPaymentRequest({ paymentRequest }) {
      const merchantHit = merchants.has(normalizeDomain(paymentRequest.merchant));
      const wallet = paymentRequest.counterparty_wallet_address
        ? normalizeWallet(paymentRequest.counterparty_wallet_address)
        : null;
      const walletHit = wallet ? wallets.has(wallet) : false;
      const checks = [
        {
          type: "merchant",
          target: paymentRequest.merchant,
          status: merchantHit ? "flagged" : "clear",
          source: "demo_screening_provider"
        }
      ];

      if (wallet) {
        checks.push({
          type: "wallet",
          target: wallet,
          status: walletHit ? "flagged" : "clear",
          source: "demo_screening_provider"
        });
      }

      return buildScreeningResult({ provider: "demo_screening_v0.2", checks });
    }
  };
}

export function createOfacDemoScreeningProvider({
  merchants = [],
  wallets = [],
  listPath = resolve(__dirname, "../../../data/ofac-demo.json")
} = {}) {
  let bundled = { merchants: [], wallets: [] };
  try {
    bundled = JSON.parse(readFileSync(listPath, "utf8"));
  } catch {
    bundled = { merchants: [], wallets: [] };
  }

  const flaggedMerchants = normalizeMerchantSet([...bundled.merchants, ...merchants]);
  const flaggedWallets = normalizeWalletSet([...bundled.wallets, ...wallets]);

  return {
    id: "ofac_demo_v0.2",
    screenPaymentRequest({ paymentRequest }) {
      const merchant = normalizeDomain(paymentRequest.merchant);
      const wallet = paymentRequest.counterparty_wallet_address
        ? normalizeWallet(paymentRequest.counterparty_wallet_address)
        : null;

      const checks = [
        {
          type: "merchant",
          target: merchant,
          status: flaggedMerchants.has(merchant) ? "flagged" : "clear",
          source: "ofac_demo_list"
        }
      ];

      if (wallet) {
        checks.push({
          type: "wallet",
          target: wallet,
          status: flaggedWallets.has(wallet) ? "flagged" : "clear",
          source: "ofac_demo_list"
        });
      }

      return buildScreeningResult({ provider: "ofac_demo_v0.2", checks });
    }
  };
}

export function createCompositeScreeningProvider(providers = []) {
  const activeProviders = providers.length
    ? providers
    : [createOfacDemoScreeningProvider(), createDemoScreeningProvider()];

  return {
    id: activeProviders.map((provider) => provider.id).join("+"),
    screenPaymentRequest(context) {
      const checks = [];
      for (const provider of activeProviders) {
        const result = provider.screenPaymentRequest(context);
        checks.push(...result.checks);
      }
      return buildScreeningResult({
        provider: activeProviders.map((provider) => provider.id).join("+"),
        checks
      });
    }
  };
}
