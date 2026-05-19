import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AgentPayGuard } from "../../../packages/core/src/index.js";
import { runScenario } from "../../../packages/core/src/demo.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "../../..");
const examplesDir = path.join(rootDir, "examples");

const DEMO_SCENARIOS = Object.freeze({
  approved: {
    id: "approved",
    label: "Run Approved Demo",
    title: "Approved Payment",
    summary: "Allowlisted API purchase stays within mandate and auto-approve limits.",
    emphasis: "approved",
    file: "payment-approved.json"
  },
  blocked: {
    id: "blocked",
    label: "Run Blocked Demo",
    title: "Blocked Payment",
    summary: "Denylisted merchant and wallet trigger a high-risk block before execution.",
    emphasis: "blocked",
    file: "payment-blocked.json"
  },
  "human-approval": {
    id: "human-approval",
    label: "Run Human Approval Demo",
    title: "Human Approval Needed",
    summary: "The amount exceeds the auto-approve threshold, so the request pauses for review.",
    emphasis: "pending_human_approval",
    file: "payment-human-approval.json"
  }
});

function createSequentialNow(startIso = "2026-05-17T09:00:00.000Z", stepMs = 60_000) {
  const start = new Date(startIso).getTime();
  let tick = 0;
  return () => new Date(start + stepMs * tick++);
}

export async function readDemoScenario(id) {
  const meta = DEMO_SCENARIOS[id];
  if (!meta) return null;
  const raw = await readFile(path.join(examplesDir, meta.file), "utf8");
  return { meta, scenario: JSON.parse(raw) };
}

export function listDemoScenarios() {
  return Object.values(DEMO_SCENARIOS).map(({ file, ...meta }) => meta);
}

export async function runDemoScenario(id) {
  const loaded = await readDemoScenario(id);
  if (!loaded) return null;

  const guard = new AgentPayGuard({ now: createSequentialNow() });
  const output = runScenario(guard, loaded.scenario, `demo:${id}`);

  return {
    scenario: loaded.meta,
    ...output
  };
}
