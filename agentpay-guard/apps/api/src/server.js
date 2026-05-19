import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AgentPayGuard } from "../../../packages/core/src/index.js";
import { listDemoScenarios, runDemoScenario } from "./demo.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "../../web");
const webAssets = new Map([
  ["/", { file: "index.html", type: "text/html; charset=utf-8" }],
  ["/styles.css", { file: "styles.css", type: "text/css; charset=utf-8" }],
  ["/app.js", { file: "app.js", type: "application/javascript; charset=utf-8" }]
]);

function parsePort(argv = process.argv, env = process.env) {
  const portFlag = argv.find((arg) => arg.startsWith("--port="));
  if (portFlag) return Number(portFlag.split("=")[1]);

  const portIndex = argv.indexOf("--port");
  if (portIndex !== -1 && argv[portIndex + 1]) return Number(argv[portIndex + 1]);

  return Number(env.PORT ?? 8787);
}

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

async function serveWebAsset(response, pathname) {
  const asset = webAssets.get(pathname);
  if (!asset) return false;
  const body = await readFile(path.join(webRoot, asset.file));
  response.writeHead(200, { "content-type": asset.type });
  response.end(body);
  return true;
}

export function createAgentPayApi(guard = new AgentPayGuard()) {
  return http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, `http://${request.headers.host}`);
      const body = request.method === "POST" ? await readBody(request) : {};

      if (request.method === "GET" && (await serveWebAsset(response, url.pathname))) {
        return;
      }

      if (request.method === "GET" && url.pathname === "/health") {
        return send(response, 200, { status: "ok" });
      }
      if (request.method === "GET" && url.pathname === "/demo/scenarios") {
        return send(response, 200, { scenarios: listDemoScenarios() });
      }
      if (
        (request.method === "GET" || request.method === "POST") &&
        url.pathname.match(/^\/demo\/run\/[^/]+$/)
      ) {
        const scenarioId = url.pathname.split("/")[3];
        const result = await runDemoScenario(scenarioId);
        return result ? send(response, 200, result) : send(response, 404, { error: "not_found" });
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
  const port = parsePort();
  createAgentPayApi().listen(port, () => {
    console.log(`AgentPay Guard API and web demo listening on http://127.0.0.1:${port}`);
  });
}
