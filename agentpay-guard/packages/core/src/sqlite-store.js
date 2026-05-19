import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { createId } from "../../shared/src/schemas.js";

function initSchema(db) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS counters (
      prefix TEXT PRIMARY KEY,
      value INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS entities (
      collection TEXT NOT NULL,
      id TEXT NOT NULL,
      data TEXT NOT NULL,
      PRIMARY KEY (collection, id)
    );

    CREATE TABLE IF NOT EXISTS kv (
      namespace TEXT NOT NULL,
      key TEXT NOT NULL,
      value TEXT NOT NULL,
      PRIMARY KEY (namespace, key)
    );

    CREATE TABLE IF NOT EXISTS audit_events (
      id TEXT PRIMARY KEY,
      type TEXT NOT NULL,
      actor TEXT NOT NULL,
      subject_id TEXT NOT NULL,
      case_id TEXT,
      input_hash TEXT NOT NULL,
      output_hash TEXT NOT NULL,
      policy_version TEXT,
      previous_event_hash TEXT,
      created_at TEXT NOT NULL,
      event_hash TEXT NOT NULL
    );

    CREATE TRIGGER IF NOT EXISTS audit_events_no_update
    BEFORE UPDATE ON audit_events
    BEGIN
      SELECT RAISE(ABORT, 'audit_events is append-only');
    END;

    CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
    BEFORE DELETE ON audit_events
    BEGIN
      SELECT RAISE(ABORT, 'audit_events is append-only');
    END;
  `);
}

function loadEntityMap(db, collection) {
  const map = new Map();
  const rows = db.prepare("SELECT id, data FROM entities WHERE collection = ?").all(collection);
  for (const row of rows) {
    map.set(row.id, JSON.parse(row.data));
  }
  return map;
}

function wrapEntityMap(db, collection, map) {
  return {
    get(id) {
      return map.get(id);
    },
    set(id, value) {
      map.set(id, value);
      db.prepare(
        `INSERT INTO entities (collection, id, data) VALUES (?, ?, ?)
         ON CONFLICT(collection, id) DO UPDATE SET data = excluded.data`
      ).run(collection, id, JSON.stringify(value));
    },
    has(id) {
      return map.has(id);
    },
    values() {
      return map.values();
    },
    entries() {
      return map.entries();
    },
    [Symbol.iterator]() {
      return map[Symbol.iterator]();
    }
  };
}

function loadKvMap(db, namespace) {
  const map = new Map();
  const rows = db.prepare("SELECT key, value FROM kv WHERE namespace = ?").all(namespace);
  for (const row of rows) {
    map.set(row.key, JSON.parse(row.value));
  }
  return map;
}

function wrapKvMap(db, namespace, map) {
  return {
    get(key) {
      return map.get(key);
    },
    set(key, value) {
      map.set(key, value);
      db.prepare(
        `INSERT INTO kv (namespace, key, value) VALUES (?, ?, ?)
         ON CONFLICT(namespace, key) DO UPDATE SET value = excluded.value`
      ).run(namespace, key, JSON.stringify(value));
    },
    has(key) {
      return map.has(key);
    }
  };
}

function loadAuditEvents(db) {
  const rows = db
    .prepare(
      `SELECT id, type, actor, subject_id, case_id, input_hash, output_hash, policy_version,
              previous_event_hash, created_at, event_hash
       FROM audit_events ORDER BY rowid ASC`
    )
    .all();

  return rows.map((row) => ({
    id: row.id,
    type: row.type,
    actor: row.actor,
    subject_id: row.subject_id,
    case_id: row.case_id,
    input_hash: row.input_hash,
    output_hash: row.output_hash,
    policy_version: row.policy_version,
    previous_event_hash: row.previous_event_hash,
    created_at: row.created_at,
    event_hash: row.event_hash
  }));
}

function createAuditEvents(db) {
  const events = loadAuditEvents(db);

  return {
    get length() {
      return events.length;
    },
    at(index) {
      return events.at(index);
    },
    push(event) {
      db.prepare(
        `INSERT INTO audit_events (
          id, type, actor, subject_id, case_id, input_hash, output_hash,
          policy_version, previous_event_hash, created_at, event_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
      ).run(
        event.id,
        event.type,
        event.actor,
        event.subject_id,
        event.case_id,
        event.input_hash,
        event.output_hash,
        event.policy_version,
        event.previous_event_hash,
        event.created_at,
        event.event_hash
      );
      events.push(event);
      return events.length;
    },
    map(callback) {
      return events.map(callback);
    },
    filter(callback) {
      return events.filter(callback);
    },
    [Symbol.iterator]() {
      return events[Symbol.iterator]();
    }
  };
}

export function createSqliteStore(dbPath = "./data/agentpay.db") {
  const absolutePath = resolve(dbPath);
  mkdirSync(dirname(absolutePath), { recursive: true });
  const db = new DatabaseSync(absolutePath);
  initSchema(db);

  const nextId = (prefix) => {
    const row = db.prepare("SELECT value FROM counters WHERE prefix = ?").get(prefix);
    const next = (row?.value ?? 0) + 1;
    db.prepare(
      `INSERT INTO counters (prefix, value) VALUES (?, ?)
       ON CONFLICT(prefix) DO UPDATE SET value = excluded.value`
    ).run(prefix, next);
    return createId(prefix, next);
  };

  return {
    kind: "sqlite",
    path: absolutePath,
    db,
    nextId,
    principals: wrapEntityMap(db, "principals", loadEntityMap(db, "principals")),
    users: wrapEntityMap(db, "users", loadEntityMap(db, "users")),
    agents: wrapEntityMap(db, "agents", loadEntityMap(db, "agents")),
    mandates: wrapEntityMap(db, "mandates", loadEntityMap(db, "mandates")),
    paymentRequests: wrapEntityMap(db, "payment_requests", loadEntityMap(db, "payment_requests")),
    policyDecisions: wrapEntityMap(db, "policy_decisions", loadEntityMap(db, "policy_decisions")),
    payments: wrapEntityMap(db, "payments", loadEntityMap(db, "payments")),
    receipts: wrapEntityMap(db, "receipts", loadEntityMap(db, "receipts")),
    cases: wrapEntityMap(db, "cases", loadEntityMap(db, "cases")),
    auditEvents: createAuditEvents(db),
    idempotency: wrapKvMap(db, "idempotency", loadKvMap(db, "idempotency")),
    merchantRequestIndex: wrapKvMap(db, "merchant_request_index", loadKvMap(db, "merchant_request_index")),
    nonceIndex: wrapKvMap(db, "nonce_index", loadKvMap(db, "nonce_index"))
  };
}
