const MAX_EVENTS = 200;

/** @type {import("./live-feed.js").AgentLiveEvent[]} */
const events = [];

/**
 * @typedef {object} AgentLiveEvent
 * @property {string} id
 * @property {string} at
 * @property {string} agent_slug
 * @property {string} agent_name
 * @property {string} phase
 * @property {string} [message]
 * @property {object} [llm]
 * @property {object} [payment_request]
 * @property {object} [decision]
 * @property {object} [receipt]
 * @property {object} [case]
 * @property {boolean} [obeyed]
 */

let sequence = 0;

export function appendLiveEvent(event) {
  const entry = {
    id: `live_${++sequence}`,
    at: new Date().toISOString(),
    ...event
  };
  events.unshift(entry);
  if (events.length > MAX_EVENTS) {
    events.length = MAX_EVENTS;
  }
  return entry;
}

export function listLiveEvents({ limit = 50, agent_slug: agentSlug } = {}) {
  let filtered = events;
  if (agentSlug) {
    filtered = filtered.filter((event) => event.agent_slug === agentSlug);
  }
  return filtered.slice(0, limit);
}

export function clearLiveEvents() {
  events.length = 0;
}

export function liveFeedStats() {
  const byAgent = {};
  for (const event of events) {
    if (event.phase !== "decision") continue;
    const slug = event.agent_slug;
    byAgent[slug] ??= { decisions: 0, approved: 0, blocked: 0, pending: 0 };
    byAgent[slug].decisions += 1;
    const status = event.decision?.status;
    if (status === "approved") byAgent[slug].approved += 1;
    else if (status === "blocked") byAgent[slug].blocked += 1;
    else byAgent[slug].pending += 1;
  }
  return { total_events: events.length, by_agent: byAgent };
}
