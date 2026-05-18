import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AgentPayGuard } from "../../../packages/core/src/index.js";

export function filterAuditEvents(events, { subjectId, caseId, type } = {}) {
  let filtered = events;
  if (subjectId) {
    filtered = filtered.filter((event) => event.subject_id === subjectId);
  }
  if (caseId) {
    filtered = filtered.filter((event) => event.case_id === caseId);
  }
  if (type) {
    filtered = filtered.filter((event) => event.type === type);
  }
  return filtered;
}

export async function readBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString("utf8");
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    const error = new Error("Invalid JSON body");
    error.name = "ValidationError";
    error.statusCode = 400;
    throw error;
  }
}

function send(response, status, payload) {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(payload, null, 2));
}

export function createAgentPayApi(guard = new AgentPayGuard()) {
  return http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, `http://${request.headers.host}`);
      const body = request.method === "POST" ? await readBody(request) : {};

      if (request.method === "GET" && url.pathname === "/health") {
        return send(response, 200, { status: "ok" });
      }
      if (request.method === "POST" && url.pathname === "/principals") return send(response, 201, guard.createPrincipal(body));
      if (request.method === "POST" && url.pathname === "/users") return send(response, 201, guard.createUser(body));
      if (request.method === "POST" && url.pathname === "/agents") return send(response, 201, guard.createAgent(body));
      if (request.method === "POST" && url.pathname === "/mandates") return send(response, 201, guard.createMandate(body));
      if (request.method === "POST" && url.pathname.match(/^\/mandates\/[^/]+\/revoke$/)) {
        return send(response, 200, guard.revokeMandate(url.pathname.split("/")[2]));
      }
      if (request.method === "POST" && url.pathname === "/payment-requests/check") return send(response, 200, guard.checkPayment(body));
      if (request.method === "POST" && url.pathname.match(/^\/payment-requests\/[^/]+\/execute-mock$/)) {
        return send(response, 200, guard.executeMockPayment(url.pathname.split("/")[2]));
      }
      if (request.method === "GET" && url.pathname.match(/^\/receipts\/[^/]+$/)) {
        const receipt = guard.getReceipt(url.pathname.split("/")[2]);
        return receipt ? send(response, 200, receipt) : send(response, 404, { error: "not_found" });
      }
      if (request.method === "GET" && url.pathname.match(/^\/evidence-packs\/[^/]+$/)) {
        return send(response, 200, guard.exportEvidencePack(url.pathname.split("/")[2]));
      }
      if (request.method === "GET" && url.pathname === "/audit-events") {
        const events = filterAuditEvents(guard.store.auditEvents, {
          subjectId: url.searchParams.get("subject_id"),
          caseId: url.searchParams.get("case_id"),
          type: url.searchParams.get("type")
        });
        return send(response, 200, events);
      }

      return send(response, 404, { error: "not_found" });
    } catch (error) {
      return send(response, error.statusCode ?? 500, {
        error: error.name,
        message: error.message,
        details: error.details ?? null
      });
    }
  });
}

const isMain =
  process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const port = Number(process.env.PORT ?? 8787);
  createAgentPayApi().listen(port, () => {
    console.log(`AgentPay Guard API listening on http://127.0.0.1:${port}`);
  });
}
