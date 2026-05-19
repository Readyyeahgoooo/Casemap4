const LOCAL_ORIGIN_PREFIXES = ["http://127.0.0.1:", "http://localhost:"];
const ALL_ROLES = ["admin", "developer", "compliance_reviewer", "finance_approver", "read_only_auditor"];
const RATE_LIMIT_WINDOW_MS = 60_000;
const rateLimitState = new Map();

function rateLimitMaxRequests() {
  return Number(process.env.AGENTPAY_RATE_LIMIT_PER_MIN ?? 120);
}

export function resetRateLimitForTests() {
  rateLimitState.clear();
}

function rateLimitKey(request) {
  return request.headers["x-agentpay-api-key"] ?? request.socket?.remoteAddress ?? "anonymous";
}

export function assertRateLimit(request) {
  const key = rateLimitKey(request);
  const now = Date.now();
  const current = rateLimitState.get(key) ?? { count: 0, windowStart: now };

  if (now - current.windowStart >= RATE_LIMIT_WINDOW_MS) {
    current.count = 0;
    current.windowStart = now;
  }

  current.count += 1;
  rateLimitState.set(key, current);

  if (current.count > rateLimitMaxRequests()) {
    const error = new Error("Rate limit exceeded");
    error.name = "TooManyRequestsError";
    error.statusCode = 429;
    throw error;
  }
}

export function getConfiguredApiKey(env = process.env) {
  const key = env.AGENTPAY_API_KEY?.trim();
  return key || null;
}

export function parseApiKeyRegistry(value) {
  if (!value) return null;
  const registry = new Map();

  for (const rawEntry of value.split(";")) {
    const entry = rawEntry.trim();
    if (!entry) continue;

    const separator = entry.includes("=") ? "=" : ":";
    const [rawKey, rawRoles] = entry.split(separator);
    const key = rawKey?.trim();
    const roles = rawRoles
      ?.split("|")
      .map((role) => role.trim())
      .filter(Boolean);

    if (key && roles?.length) {
      registry.set(key, roles);
    }
  }

  return registry.size ? registry : null;
}

export function getConfiguredApiKeyRegistry(env = process.env) {
  const scoped = parseApiKeyRegistry(env.AGENTPAY_API_KEYS);
  if (scoped) return scoped;

  const legacy = getConfiguredApiKey(env);
  return legacy ? new Map([[legacy, ALL_ROLES]]) : null;
}

function normalizeApiKeyRegistry(apiKeyOrRegistry) {
  if (!apiKeyOrRegistry) return null;
  if (typeof apiKeyOrRegistry === "string") {
    return new Map([[apiKeyOrRegistry, ALL_ROLES]]);
  }
  if (apiKeyOrRegistry instanceof Map) {
    return apiKeyOrRegistry;
  }
  return new Map(
    Object.entries(apiKeyOrRegistry).map(([key, roles]) => [
      key,
      Array.isArray(roles) ? roles : String(roles).split("|")
    ])
  );
}

export function isPublicApiPath(method, pathname) {
  if (method === "GET" && (pathname === "/" || pathname === "/health")) return true;
  if (method === "GET" && (pathname === "/styles.css" || pathname === "/app.js")) return true;
  if (method === "GET" && pathname.startsWith("/demo/")) return true;
  return false;
}

export function requiredRolesForRoute(method, pathname) {
  if (method === "POST" && (pathname === "/principals" || pathname === "/users")) return ["admin"];
  if (method === "POST" && pathname === "/agents") return ["admin", "developer"];
  if (method === "POST" && pathname === "/mandates") return ["admin", "finance_approver"];
  if (method === "POST" && pathname.match(/^\/mandates\/[^/]+\/revoke$/)) return ["admin", "finance_approver"];
  if (method === "POST" && pathname === "/payment-requests/check") return ["admin", "developer"];
  if (method === "POST" && pathname.match(/^\/payment-requests\/[^/]+\/execute-mock$/)) return ["admin", "finance_approver"];
  if (method === "GET" && pathname.match(/^\/receipts\/[^/]+$/)) return ALL_ROLES;
  if (method === "GET" && pathname.match(/^\/evidence-packs\/[^/]+$/)) {
    return ["admin", "compliance_reviewer", "finance_approver", "read_only_auditor"];
  }
  if (method === "GET" && (pathname === "/audit-events" || pathname === "/audit-events/verify")) {
    return ["admin", "compliance_reviewer", "read_only_auditor"];
  }
  return ["admin"];
}

export function assertApiKey(request, apiKeyOrRegistry, requiredRoles = []) {
  const registry = normalizeApiKeyRegistry(apiKeyOrRegistry);
  if (!registry) return { authenticated: false, roles: [] };

  const provided = request.headers["x-agentpay-api-key"];
  const roles = registry.get(provided);
  if (!roles) {
    const error = new Error("Invalid or missing x-agentpay-api-key");
    error.name = "UnauthorizedError";
    error.statusCode = 401;
    throw error;
  }

  if (requiredRoles.length && !requiredRoles.some((role) => roles.includes(role))) {
    const error = new Error("API key is not authorized for this route");
    error.name = "ForbiddenError";
    error.statusCode = 403;
    throw error;
  }

  return { authenticated: true, roles };
}

export function applyCors(request, response) {
  const origin = request.headers.origin;
  if (!origin) return;

  const allowed = LOCAL_ORIGIN_PREFIXES.some((prefix) => origin.startsWith(prefix));
  if (allowed) {
    response.setHeader("Access-Control-Allow-Origin", origin);
    response.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
    response.setHeader("Access-Control-Allow-Headers", "content-type,x-agentpay-api-key");
    response.setHeader("Vary", "Origin");
    return;
  }

  response.setHeader("Vary", "Origin");
}

export function handlePreflight(request, response) {
  if (request.method !== "OPTIONS") return false;
  applyCors(request, response);
  response.writeHead(204);
  response.end();
  return true;
}
