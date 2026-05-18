import { createHash } from "node:crypto";

export function canonicalize(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }

  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalize(item)).join(",")}]`;
  }

  const entries = Object.entries(value)
    .filter(([, entryValue]) => entryValue !== undefined)
    .sort(([left], [right]) => left.localeCompare(right));

  return `{${entries
    .map(([key, entryValue]) => `${JSON.stringify(key)}:${canonicalize(entryValue)}`)
    .join(",")}}`;
}

export function sha256(value) {
  const input = typeof value === "string" ? value : canonicalize(value);
  return `sha256:${createHash("sha256").update(input).digest("hex")}`;
}

export function paymentRequestHash(request) {
  return sha256({
    agent_id: request.agent_id,
    mandate_id: request.mandate_id ?? null,
    merchant: request.merchant,
    amount_usd: request.amount_usd,
    token: request.token,
    chain: request.chain,
    purpose: request.purpose,
    merchant_request_id: request.merchant_request_id ?? null,
    nonce: request.nonce ?? null,
    counterparty_wallet_address: request.counterparty_wallet_address ?? null
  });
}
