import { appendLiveEvent } from "./live-feed.js";

/** @type {import("./demo-agents.js").DemoAgentWorld | null} */
let seededWorld = null;

/** @type {Map<string, object>} */
const pendingDemoMeta = new Map();

export function extractDemoMeta(body = {}) {
  const {
    demo_agent_slug,
    demo_agent_name,
    demo_llm,
    ...paymentBody
  } = body;
  return {
    paymentBody,
    demoMeta: {
      demo_agent_slug: demo_agent_slug ?? null,
      demo_agent_name: demo_agent_name ?? null,
      demo_llm: demo_llm ?? null
    }
  };
}

export function stashDemoMeta(paymentRequestId, demoMeta) {
  if (!demoMeta?.demo_agent_slug) return;
  pendingDemoMeta.set(paymentRequestId, demoMeta);
}

export function takeDemoMeta(paymentRequestId) {
  const meta = pendingDemoMeta.get(paymentRequestId);
  pendingDemoMeta.delete(paymentRequestId);
  return meta;
}

/**
 * @typedef {object} DemoAgentRecord
 * @property {string} slug
 * @property {string} name
 * @property {string} role
 * @property {string} agent_id
 * @property {string} mandate_id
 * @property {string} principal_id
 * @property {string} description
 */

/**
 * @typedef {object} DemoAgentWorld
 * @property {string} principal_id
 * @property {string} user_id
 * @property {string} user_email
 * @property {DemoAgentRecord[]} agents
 */

const AGENT_DEFINITIONS = [
  {
    slug: "procurement",
    name: "ProcurementBot",
    role: "office_procurement",
    description: "Buys office supplies from approved vendors under $20 auto-approve.",
    agent: {
      name: "ProcurementBot",
      type: "autonomous_procurement",
      wallet_address: "0xabc0000000000000000000000000000000000001",
      chain: "base"
    },
    mandate: {
      allowed_actions: ["buy_office_supplies"],
      allowed_merchants: ["staples.demo", "supplies.vendor.com", "paperworld.demo"],
      denied_merchants: ["blocked.vendor.com"],
      allowed_tokens: ["USDC"],
      allowed_chains: ["base"],
      denied_wallets: [],
      limits: {
        auto_approve_limit_usd: 20,
        human_approval_limit_usd: 100,
        hard_block_limit_usd: 500,
        daily_limit_usd: 1000
      },
      expires_at: "2027-12-31T23:59:59.000Z"
    }
  },
  {
    slug: "research",
    name: "ResearchBot",
    role: "research_procurement",
    description: "Purchases API credits and datasets; may probe risky vendors or wallets.",
    agent: {
      name: "ResearchBot",
      type: "autonomous_api_buyer",
      wallet_address: "0xabc0000000000000000000000000000000000002",
      chain: "base"
    },
    mandate: {
      allowed_actions: ["buy_api_credits", "purchase_dataset"],
      allowed_merchants: [
        "api.vendor.com",
        "data.market.demo",
        "sanctioned-example.test",
        "modelhub.demo"
      ],
      denied_merchants: ["blocked.vendor.com"],
      allowed_tokens: ["USDC"],
      allowed_chains: ["base"],
      denied_wallets: ["0xdead000000000000000000000000000000000000"],
      limits: {
        auto_approve_limit_usd: 20,
        human_approval_limit_usd: 100,
        hard_block_limit_usd: 500,
        daily_limit_usd: 1000
      },
      expires_at: "2027-12-31T23:59:59.000Z"
    }
  },
  {
    slug: "travel",
    name: "TravelBot",
    role: "travel_booking",
    description: "Books hotels and flights; amounts often exceed auto-approve limits.",
    agent: {
      name: "TravelBot",
      type: "autonomous_travel_booker",
      wallet_address: "0xabc0000000000000000000000000000000000003",
      chain: "base"
    },
    mandate: {
      allowed_actions: ["book_travel"],
      allowed_merchants: ["hotels.demo", "flights.demo", "rail.demo"],
      denied_merchants: ["blocked.vendor.com"],
      allowed_tokens: ["USDC"],
      allowed_chains: ["base"],
      denied_wallets: [],
      limits: {
        auto_approve_limit_usd: 20,
        human_approval_limit_usd: 150,
        hard_block_limit_usd: 800,
        daily_limit_usd: 2000
      },
      expires_at: "2027-12-31T23:59:59.000Z"
    }
  }
];

export function getDemoAgentWorld() {
  return seededWorld;
}

export function seedDemoAgents(guard) {
  const principal = guard.createPrincipal(
    {
      type: "company",
      legal_name: "Acme Demo Holdings",
      jurisdiction: "HK",
      company_number: "DEMO-ACME-001"
    },
    "demo:seed"
  );
  const user = guard.createUser(
    {
      principal_id: principal.id,
      email: "cfo@acme.demo",
      role: "finance_approver"
    },
    "demo:seed"
  );

  const agents = AGENT_DEFINITIONS.map((definition) => {
    const agent = guard.createAgent(
      { ...definition.agent, principal_id: principal.id },
      "demo:seed"
    );
    const mandate = guard.createMandate(
      {
        ...definition.mandate,
        agent_id: agent.id,
        principal_id: principal.id,
        signed_by: user.email
      },
      "demo:seed"
    );

    return {
      slug: definition.slug,
      name: definition.name,
      role: definition.role,
      description: definition.description,
      agent_id: agent.id,
      mandate_id: mandate.id,
      principal_id: principal.id
    };
  });

  seededWorld = {
    principal_id: principal.id,
    user_id: user.id,
    user_email: user.email,
    agents
  };

  appendLiveEvent({
    agent_slug: "system",
    agent_name: "AgentPay Guard",
    phase: "seed",
    message: `Seeded ${agents.length} demo agents for ${principal.legal_name}.`
  });

  return seededWorld;
}

export function recordAgentPaymentFlow({
  agent_slug,
  agent_name,
  phase,
  message,
  llm,
  payment_request,
  decision,
  receipt,
  review_case,
  obeyed
}) {
  return appendLiveEvent({
    agent_slug,
    agent_name,
    phase,
    message,
    llm,
    payment_request,
    decision,
    receipt,
    case: review_case ?? null,
    obeyed
  });
}
