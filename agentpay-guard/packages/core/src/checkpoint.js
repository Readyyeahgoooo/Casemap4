import { appendFileSync, mkdirSync, readFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { sha256 } from "../../shared/src/hash.js";

const CHECKPOINT_INTERVAL = Number(process.env.AGENTPAY_CHECKPOINT_INTERVAL ?? 25);

export function checkpointFilePath(path = process.env.AGENTPAY_CHECKPOINT_FILE ?? "./data/audit-checkpoints.jsonl") {
  return resolve(path);
}

export function computeAuditCheckpointRoot(events) {
  return sha256({
    count: events.length,
    event_hashes: events.map((event) => event.event_hash)
  });
}

export function maybeAppendAuditCheckpoint(events, { now = () => new Date(), path } = {}) {
  if (!events.length || events.length % CHECKPOINT_INTERVAL !== 0) {
    return null;
  }

  const filePath = checkpointFilePath(path);
  mkdirSync(dirname(filePath), { recursive: true });
  const checkpoint = {
    checkpoint_version: "agentpay-audit-checkpoint-v0.1",
    created_at: now().toISOString(),
    event_count: events.length,
    root_hash: computeAuditCheckpointRoot(events),
    latest_event_hash: events.at(-1)?.event_hash ?? null
  };
  appendFileSync(filePath, `${JSON.stringify(checkpoint)}\n`, "utf8");
  return checkpoint;
}

export function readLatestAuditCheckpoint(path = process.env.AGENTPAY_CHECKPOINT_FILE) {
  const filePath = checkpointFilePath(path);
  if (!existsSync(filePath)) return null;

  const lines = readFileSync(filePath, "utf8")
    .trim()
    .split("\n")
    .filter(Boolean);
  if (!lines.length) return null;
  return JSON.parse(lines.at(-1));
}
