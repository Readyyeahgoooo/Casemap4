import assert from "node:assert/strict";
import test from "node:test";
import { AgentPayGuard } from "../packages/core/src/index.js";
import { createAgentPayApi } from "../apps/api/src/server.js";
import { seedDemoAgents, getDemoAgentWorld } from "../apps/api/src/demo-agents.js";
import { clearLiveEvents } from "../apps/api/src/live-feed.js";

function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ baseUrl: `http://127.0.0.1:${port}`, close: () => new Promise((r) => server.close(r)) });
    });
  });
}

async function request(baseUrl, path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, options);
  const body = await response.json();
  return { status: response.status, body };
}

test("seedDemoAgents creates three demo agents", () => {
  clearLiveEvents();
  const guard = new AgentPayGuard();
  const world = seedDemoAgents(guard);
  assert.equal(world.agents.length, 3);
  assert.ok(world.agents.some((agent) => agent.slug === "research"));
  assert.equal(getDemoAgentWorld().principal_id, world.principal_id);
});

test("API records live feed when demo agents submit payments", async () => {
  clearLiveEvents();
  const guard = new AgentPayGuard();
  seedDemoAgents(guard);
  const research = getDemoAgentWorld().agents.find((agent) => agent.slug === "research");

  const server = createAgentPayApi(guard);
  const { baseUrl, close } = await listen(server);
  try {
    const checked = await request(baseUrl, "/payment-requests/check", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        agent_id: research.agent_id,
        mandate_id: research.mandate_id,
        merchant: "sanctioned-example.test",
        amount_usd: "8.00",
        token: "USDC",
        chain: "base",
        purpose: "buy_api_credits",
        idempotency_key: "live_feed_test_1",
        merchant_request_id: "live_feed_vendor_1",
        nonce: "live_feed_nonce_1",
        demo_agent_slug: "research",
        demo_agent_name: "ResearchBot",
        demo_llm: { provider: "test", item_description: "test dataset" }
      })
    });

    assert.equal(checked.status, 200);
    assert.equal(checked.body.decision.status, "blocked");

    const feed = await request(baseUrl, "/demo/live-feed");
    assert.equal(feed.status, 200);
    assert.ok(feed.body.events.length >= 1);
    assert.equal(feed.body.events[0].agent_slug, "research");
    assert.equal(feed.body.events[0].decision.status, "blocked");
  } finally {
    await close();
  }
});

test("POST /demo/seed-agents via HTTP", async () => {
  clearLiveEvents();
  const guard = new AgentPayGuard();
  const server = createAgentPayApi(guard);
  const { baseUrl, close } = await listen(server);
  try {
    const seeded = await request(baseUrl, "/demo/seed-agents", { method: "POST" });
    assert.equal(seeded.status, 201);
    assert.equal(seeded.body.agents.length, 3);

    const agents = await request(baseUrl, "/demo/agents");
    assert.equal(agents.status, 200);
    assert.equal(agents.body.seeded, true);
  } finally {
    await close();
  }
});
