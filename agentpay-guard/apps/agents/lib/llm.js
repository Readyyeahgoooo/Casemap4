import { CATALOGS, pickRandom, randomAmount } from "./catalogs.js";

function resolveProvider(env = process.env) {
  const explicit = env.AGENTPAY_LLM_PROVIDER?.trim().toLowerCase();
  if (explicit === "heuristic" || explicit === "offline") return "heuristic";
  if (explicit === "anthropic" && env.ANTHROPIC_API_KEY) return "anthropic";
  if (explicit === "openai" && env.OPENAI_API_KEY) return "openai";
  if (env.OPENAI_API_KEY) return "openai";
  if (env.ANTHROPIC_API_KEY) return "anthropic";
  return "heuristic";
}

function buildPrompt(agentSlug, agentRecord) {
  const catalog = CATALOGS[agentSlug];
  const vendorLines = catalog.vendors
    .map((vendor) => {
      const walletNote = vendor.wallet ? ` wallet=${vendor.wallet}` : "";
      return `- ${vendor.merchant}: ${vendor.items.join(", ")}${walletNote}`;
    })
    .join("\n");

  return `You are ${agentRecord.name}, an autonomous procurement agent for Acme Demo Holdings.
Role: ${agentRecord.description}

Choose ONE realistic purchase from the catalog below. Return JSON only, no markdown:
{
  "merchant": "domain only",
  "amount_usd": "decimal string like 12.50",
  "purpose": "one of: ${catalog.purposes.join(", ")}",
  "item_description": "short string",
  "counterparty_wallet_address": "optional EVM address or null",
  "reasoning": "one sentence why this purchase is needed now"
}

Allowed purposes: ${catalog.purposes.join(", ")}
Catalog:
${vendorLines}

Token: USDC. Chain: base. Stay within plausible amounts for this agent type.`;
}

function heuristicPlan(agentSlug, agentRecord) {
  const catalog = CATALOGS[agentSlug];
  const vendor = pickRandom(catalog.vendors);
  const item = pickRandom(vendor.items);
  return {
    merchant: vendor.merchant,
    amount_usd: randomAmount(catalog.amount_range),
    purpose: pickRandom(catalog.purposes),
    item_description: item,
    counterparty_wallet_address: vendor.wallet ?? null,
    reasoning: `${agentRecord.name} selected ${item} from ${vendor.merchant} (offline heuristic planner).`,
    provider: "heuristic",
    model: "local-catalog-v1"
  };
}

async function callOpenAi(prompt, env) {
  const model = env.OPENAI_MODEL ?? "gpt-4o-mini";
  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.OPENAI_API_KEY}`,
      "content-type": "application/json"
    },
    body: JSON.stringify({
      model,
      temperature: 0.7,
      response_format: { type: "json_object" },
      messages: [
        {
          role: "system",
          content: "You output strict JSON purchase plans for a corporate spending agent."
        },
        { role: "user", content: prompt }
      ]
    })
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`OpenAI ${response.status}: ${text}`);
  }

  const payload = await response.json();
  const content = payload.choices?.[0]?.message?.content;
  const plan = JSON.parse(content);
  return { ...plan, provider: "openai", model };
}

async function callAnthropic(prompt, env) {
  const model = env.ANTHROPIC_MODEL ?? "claude-sonnet-4-20250514";
  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json"
    },
    body: JSON.stringify({
      model,
      max_tokens: 400,
      temperature: 0.7,
      system: "You output strict JSON purchase plans for a corporate spending agent.",
      messages: [{ role: "user", content: prompt }]
    })
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Anthropic ${response.status}: ${text}`);
  }

  const payload = await response.json();
  const content = payload.content?.find((part) => part.type === "text")?.text ?? "{}";
  const jsonText = content.replace(/^```json\s*/i, "").replace(/```$/i, "").trim();
  const plan = JSON.parse(jsonText);
  return { ...plan, provider: "anthropic", model };
}

export async function planPurchase(agentSlug, agentRecord, env = process.env) {
  const provider = resolveProvider(env);
  if (provider === "heuristic") {
    return heuristicPlan(agentSlug, agentRecord);
  }

  const prompt = buildPrompt(agentSlug, agentRecord);
  try {
    if (provider === "openai") {
      return await callOpenAi(prompt, env);
    }
    return await callAnthropic(prompt, env);
  } catch (error) {
    console.warn(`[${agentSlug}] LLM failed (${error.message}); falling back to heuristic planner.`);
    return heuristicPlan(agentSlug, agentRecord);
  }
}

export function describeLlmMode(env = process.env) {
  const provider = resolveProvider(env);
  if (provider === "heuristic") {
    return "heuristic (no API key — uses local catalog)";
  }
  if (provider === "openai") {
    return `openai (${env.OPENAI_MODEL ?? "gpt-4o-mini"})`;
  }
  return `anthropic (${env.ANTHROPIC_MODEL ?? "claude-sonnet-4-20250514"})`;
}
