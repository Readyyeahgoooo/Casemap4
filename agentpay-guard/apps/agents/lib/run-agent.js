import { checkPayment, ensureDemoWorldSeeded, executeMockPayment } from "./api-client.js";
import { randomId } from "./catalogs.js";
import { describeLlmMode, planPurchase } from "./llm.js";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function log(agentSlug, message) {
  const stamp = new Date().toISOString().slice(11, 19);
  console.log(`[${stamp}] [${agentSlug}] ${message}`);
}

export async function runAgentLoop(agentSlug, { intervalMs = 12_000, once = false, env = process.env } = {}) {
  const world = await ensureDemoWorldSeeded(env);
  const agentRecord = world.agents.find((agent) => agent.slug === agentSlug);
  if (!agentRecord) {
    throw new Error(`Unknown demo agent slug: ${agentSlug}`);
  }

  log(agentSlug, `online — ${describeLlmMode(env)}`);
  log(agentSlug, `API ${env.AGENTPAY_API_URL ?? "http://127.0.0.1:5173"} | agent_id=${agentRecord.agent_id}`);

  do {
    try {
      log(agentSlug, "planning purchase...");
      const plan = await planPurchase(agentSlug, agentRecord, env);
      log(agentSlug, `intent: ${plan.item_description} @ ${plan.merchant} for $${plan.amount_usd}`);
      log(agentSlug, `reasoning: ${plan.reasoning}`);

      const payment = {
        merchant: plan.merchant,
        amount_usd: String(plan.amount_usd),
        token: "USDC",
        chain: "base",
        purpose: plan.purpose,
        counterparty_wallet_address: plan.counterparty_wallet_address ?? undefined,
        merchant_request_id: randomId(`${agentSlug}_mreq`),
        nonce: randomId(`${agentSlug}_nonce`),
        idempotency_key: randomId(`${agentSlug}_idem`),
        decision_ttl: "PT10M",
        demo_agent_slug: agentSlug,
        demo_agent_name: agentRecord.name,
        demo_llm: {
          provider: plan.provider,
          model: plan.model,
          item_description: plan.item_description,
          reasoning: plan.reasoning
        }
      };

      const result = await checkPayment(agentRecord, payment, env);
      const status = result.decision.status;
      const reason = result.decision.reason;
      log(agentSlug, `guard decision: ${status} (${reason})`);

      if (status === "approved") {
        const executed = await executeMockPayment(result.payment_request.id, env);
        log(agentSlug, `obeyed guard: executed mock payment ${executed.payment?.id ?? "ok"}`);
        log(agentSlug, `receipt ${executed.receipt?.id ?? "n/a"}`);
      } else if (status === "blocked") {
        log(agentSlug, "obeyed guard: did NOT pay (blocked)");
      } else {
        log(agentSlug, `obeyed guard: did NOT pay (${status} — awaiting human review)`);
      }
    } catch (error) {
      log(agentSlug, `error: ${error.message}`);
      if (error.payload) {
        console.error(JSON.stringify(error.payload, null, 2));
      }
    }

    if (once) break;
    await sleep(intervalMs);
  } while (true);
}
