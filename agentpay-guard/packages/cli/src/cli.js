#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { AgentPayGuard } from "../../core/src/index.js";
import { verifyAuditChain } from "../../core/src/audit.js";

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

function seedScenario(guard, scenario) {
  const principal = guard.createPrincipal(scenario.principal);
  const user = guard.createUser({ ...scenario.user, principal_id: principal.id });
  const agent = guard.createAgent({ ...scenario.agent, principal_id: principal.id });
  const mandate = guard.createMandate({
    ...scenario.mandate,
    agent_id: agent.id,
    principal_id: principal.id,
    signed_by: scenario.mandate.signed_by ?? user.email
  });
  return { principal, user, agent, mandate };
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
  const seeded = seedScenario(guard, scenario);
  const paymentRequest = {
    ...scenario.payment_request,
    agent_id: seeded.agent.id,
    mandate_id: seeded.mandate.id
  };

  const result = guard.checkPayment(paymentRequest, scenario.actor ?? "cli");

  if (command === "policy:test") {
    console.log(JSON.stringify(result.decision, null, 2));
    process.exit(result.decision.status === (scenario.expected_decision_status ?? result.decision.status) ? 0 : 2);
  }

  if (command === "payment:check") {
    let execution = null;
    if (result.decision.status === "approved") {
      execution = guard.executeMockPayment(result.payment_request.id, scenario.actor ?? "cli");
    }
    const evidencePack = guard.exportEvidencePack(result.payment_request.id);
    console.log(JSON.stringify({ ...result, execution, evidence_pack: evidencePack }, null, 2));
    process.exit(0);
  }

  console.error(`Unknown command: ${command}`);
  process.exit(1);
}

main().catch((error) => {
  console.error(JSON.stringify({ error: error.name, message: error.message, details: error.details ?? null }, null, 2));
  process.exit(error.statusCode === 409 ? 2 : 1);
});
