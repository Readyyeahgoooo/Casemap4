import { createMemoryStore } from "./store.js";
import { createSqliteStore } from "./sqlite-store.js";

export function createStore(options = {}) {
  const kind = options.kind ?? process.env.AGENTPAY_STORE ?? "memory";
  if (kind === "sqlite") {
    return createSqliteStore(options.path ?? process.env.AGENTPAY_DB_PATH ?? "./data/agentpay.db");
  }
  return createMemoryStore();
}
