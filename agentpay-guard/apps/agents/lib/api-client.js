export function apiBaseUrl(env = process.env) {
  return (env.AGENTPAY_API_URL ?? "http://127.0.0.1:5173").replace(/\/$/, "");
}

export function apiHeaders(env = process.env) {
  const headers = { "content-type": "application/json" };
  if (env.AGENTPAY_API_KEY) {
    headers["x-agentpay-api-key"] = env.AGENTPAY_API_KEY;
  }
  return headers;
}

export async function apiRequest(path, { method = "GET", body, env = process.env } = {}) {
  const response = await fetch(`${apiBaseUrl(env)}${path}`, {
    method,
    headers: apiHeaders(env),
    body: body === undefined ? undefined : JSON.stringify(body)
  });

  const text = await response.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { raw: text };
  }

  if (!response.ok) {
    const error = new Error(payload?.message ?? `API ${response.status} on ${path}`);
    error.name = payload?.error ?? "ApiError";
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

export async function ensureDemoWorldSeeded(env = process.env) {
  const existing = await apiRequest("/demo/agents", { env });
  if (existing.seeded && existing.agents?.length) {
    return existing;
  }
  return apiRequest("/demo/seed-agents", { method: "POST", env });
}

export async function checkPayment(agentRecord, payment, env = process.env) {
  return apiRequest("/payment-requests/check", {
    method: "POST",
    env,
    body: {
      ...payment,
      agent_id: agentRecord.agent_id,
      mandate_id: agentRecord.mandate_id,
      demo_agent_slug: agentRecord.slug,
      demo_agent_name: agentRecord.name
    }
  });
}

export async function executeMockPayment(paymentRequestId, env = process.env) {
  return apiRequest(`/payment-requests/${paymentRequestId}/execute-mock`, {
    method: "POST",
    env,
    body: {}
  });
}
