import { generateKeyPairSync, sign, verify } from "node:crypto";
import { sha256 } from "./hash.js";

export const MANDATE_SIGNATURE_TYPE = "ed25519_v0.1";

export function generateSigningKeyPair() {
  const { publicKey, privateKey } = generateKeyPairSync("ed25519");
  return {
    publicKey: publicKey.export({ type: "spki", format: "der" }).toString("base64"),
    privateKey: privateKey.export({ type: "pkcs8", format: "der" }).toString("base64")
  };
}

export function mandateSigningPayload(mandate) {
  return {
    agent_id: mandate.agent_id,
    principal_id: mandate.principal_id,
    signer_user_id: mandate.signer_user_id,
    allowed_actions: [...(mandate.allowed_actions ?? [])].sort(),
    allowed_merchants: [...(mandate.allowed_merchants ?? [])].sort(),
    denied_merchants: [...(mandate.denied_merchants ?? [])].sort(),
    allowed_tokens: [...(mandate.allowed_tokens ?? [])].sort(),
    allowed_chains: [...(mandate.allowed_chains ?? [])].sort(),
    denied_wallets: [...(mandate.denied_wallets ?? [])].sort(),
    limits: mandate.limits,
    expires_at: mandate.expires_at,
    signed_by: mandate.signed_by,
    status: mandate.status ?? "active"
  };
}

export function mandateHash(mandate) {
  return sha256(mandateSigningPayload(mandate));
}

export function signMandateHash(mandateHashValue, privateKeyBase64) {
  const privateKey = Buffer.from(privateKeyBase64, "base64");
  const signature = sign(null, Buffer.from(mandateHashValue, "utf8"), {
    key: privateKey,
    format: "der",
    type: "pkcs8"
  });
  return signature.toString("base64");
}

export function verifyMandateSignature(mandate) {
  if (!mandate?.mandate_hash || !mandate?.signature || !mandate?.signer_public_key) {
    return { valid: false, reason: "missing_signature_fields" };
  }

  if (mandate.signature_type !== MANDATE_SIGNATURE_TYPE) {
    return { valid: false, reason: "unsupported_signature_type" };
  }

  const expectedHash = mandateHash(mandate);
  if (expectedHash !== mandate.mandate_hash) {
    return { valid: false, reason: "mandate_hash_mismatch", expected: expectedHash, actual: mandate.mandate_hash };
  }

  try {
    const valid = verify(
      null,
      Buffer.from(mandate.mandate_hash, "utf8"),
      {
        key: Buffer.from(mandate.signer_public_key, "base64"),
        format: "der",
        type: "spki"
      },
      Buffer.from(mandate.signature, "base64")
    );
    return valid ? { valid: true } : { valid: false, reason: "signature_invalid" };
  } catch {
    return { valid: false, reason: "signature_verify_error" };
  }
}
