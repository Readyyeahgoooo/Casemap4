#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { AgentPayGuard } from "../../core/src/index.js";
import { runScenario } from "../../core/src/demo.js";
import { verifyAuditChain } from "../../core/src/audit.js";

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

async function main() {
  const [command, filePath] = process.argv.slice(2);
  if (!command || !filePath) {
    console.error("Usage: agentpay <policy:test|payment:check|audit:verify> <json-file>");
    process.exit(1);
  }

  if (command === "audit:verify") {
    const evidencePack = await readJson(filePath);
    const result = verifyAuditChain(evidencePack.audit_events ?? []);
    console.log(JSON.stringify(result, null, 2));
    process.exit(result.valid ? 0 : 2);
  }

  const scenario = await readJson(filePath);
  const guard = new AgentPayGuard();
  const output = runScenario(guard, scenario, scenario.actor ?? "cli");

  if (command === "policy:test") {
    console.log(JSON.stringify(output.result.decision, null, 2));
    process.exit(output.result.decision.status === (scenario.expected_decision_status ?? output.result.decision.status) ? 0 : 2);
  }

  if (command === "payment:check") {
    console.log(JSON.stringify(output, null, 2));
    process.exit(0);
  }

  console.error(`Unknown command: ${command}`);
  process.exit(1);
}

main().catch((error) => {
  console.error(JSON.stringify({ error: error.name, message: error.message, details: error.details ?? null }, null, 2));
  process.exit(error.statusCode === 409 ? 2 : 1);
});
