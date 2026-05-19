import { ValidationError } from "./schemas.js";

const DEFAULT_DECISION_TTL = "PT10M";
const MAX_TTL_MS = 24 * 60 * 60 * 1000;

export function parseIsoDurationMs(value, { defaultValue = DEFAULT_DECISION_TTL } = {}) {
  const ttl = value ?? defaultValue;
  const match = /^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/.exec(ttl);
  if (!match) {
    throw new ValidationError("Invalid decision_ttl", {
      decision_ttl: ttl,
      expected: "ISO duration like PT10M, PT1H, PT30S"
    });
  }

  const hours = Number(match[1] ?? 0);
  const minutes = Number(match[2] ?? 0);
  const seconds = Number(match[3] ?? 0);
  const ms = ((hours * 60 * 60) + (minutes * 60) + seconds) * 1000;

  if (ms <= 0 || ms > MAX_TTL_MS) {
    throw new ValidationError("decision_ttl out of allowed range", {
      decision_ttl: ttl,
      min: "PT1S",
      max: "PT24H"
    });
  }

  return ms;
}

export function normalizeDecisionTtl(value) {
  if (!value) return DEFAULT_DECISION_TTL;
  parseIsoDurationMs(value);
  return value;
}
