import { domainToASCII } from "node:url";

export const ROLES = Object.freeze([
  "admin",
  "developer",
  "compliance_reviewer",
  "finance_approver",
  "read_only_auditor"
]);

export const DECISION_STATUSES = Object.freeze([
  "approved",
  "pending_human_approval",
  "manual_review",
  "blocked"
]);

export class ValidationError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "ValidationError";
    this.details = details;
    this.statusCode = 400;
  }
}

export class ConflictError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "ConflictError";
    this.details = details;
    this.statusCode = 409;
  }
}

export function requireFields(input, fields, label) {
  for (const field of fields) {
    if (input[field] === undefined || input[field] === null || input[field] === "") {
      throw new ValidationError(`${label}.${field} is required`, { field });
    }
  }
}

export function ensureRole(role) {
  if (!ROLES.includes(role)) {
    throw new ValidationError(`Unknown role: ${role}`, { allowed: ROLES });
  }
}

export function ensurePositiveAmount(amount, field = "amount_usd") {
  const parsed = Number(amount);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new ValidationError(`${field} must be a positive number`, { field, amount });
  }
  return parsed;
}

export function normalizeDomain(value) {
  const raw = String(value).trim().toLowerCase();
  const withoutProtocol = raw.replace(/^https?:\/\//, "").split("/")[0].split(":")[0];
  const ascii = domainToASCII(withoutProtocol);
  if (!ascii) {
    throw new ValidationError("Invalid merchant domain", { value });
  }
  return ascii;
}

export function normalizeWallet(value) {
  if (value === undefined || value === null || value === "") return null;
  const address = String(value).trim();
  if (!/^0x[a-fA-F0-9]{40}$/.test(address)) {
    throw new ValidationError("Invalid EVM wallet address", { value });
  }
  return address.toLowerCase();
}

export function createId(prefix, counter) {
  return `${prefix}_${String(counter).padStart(6, "0")}`;
}
