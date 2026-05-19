import { createId } from "../../shared/src/schemas.js";

export function createMemoryStore() {
  const counters = new Map();
  const nextId = (prefix) => {
    const next = (counters.get(prefix) ?? 0) + 1;
    counters.set(prefix, next);
    return createId(prefix, next);
  };

  return {
    nextId,
    principals: new Map(),
    users: new Map(),
    agents: new Map(),
    mandates: new Map(),
    paymentRequests: new Map(),
    policyDecisions: new Map(),
    payments: new Map(),
    receipts: new Map(),
    cases: new Map(),
    auditEvents: [],
    idempotency: new Map(),
    merchantRequestIndex: new Map(),
    nonceIndex: new Map()
  };
}
