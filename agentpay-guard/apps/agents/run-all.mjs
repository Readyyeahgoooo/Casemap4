#!/usr/bin/env node
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { ensureDemoWorldSeeded } from "./lib/api-client.js";
import { describeLlmMode } from "./lib/llm.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const agentsDir = __dirname;

const agentScripts = [
  { slug: "procurement", file: "procurement-agent.mjs" },
  { slug: "research", file: "research-agent.mjs" },
  { slug: "travel", file: "travel-agent.mjs" }
];

const mode = process.argv.includes("--sequential") ? "sequential" : "parallel";
const once = process.argv.includes("--once");

async function main() {
  const world = await ensureDemoWorldSeeded();
  console.log("AgentPay Guard demo agents");
  console.log(`API: ${process.env.AGENTPAY_API_URL ?? "http://127.0.0.1:5173"}`);
  console.log(`LLM: ${describeLlmMode()}`);
  console.log(`Seeded principal ${world.principal_id} with ${world.agents.length} agents`);
  console.log("Open the web console → Live Agent Feed to watch decisions in real time.\n");

  if (mode === "sequential") {
    for (const agent of agentScripts) {
      console.log(`\n=== Running ${agent.slug} once ===`);
      await runNode(agent.file, ["--once"]);
    }
    return;
  }

  console.log("Starting three agent processes (Ctrl+C stops all)...\n");
  const children = agentScripts.map((agent) => {
    const child = spawn(process.execPath, [path.join(agentsDir, agent.file), ...(once ? ["--once"] : [])], {
      stdio: "inherit",
      env: process.env
    });
    child.on("exit", (code) => {
      console.log(`[supervisor] ${agent.slug} exited with code ${code ?? 0}`);
    });
    return child;
  });

  const shutdown = () => {
    for (const child of children) child.kill("SIGTERM");
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

function runNode(file, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(agentsDir, file), ...args], {
      stdio: "inherit",
      env: process.env
    });
    child.on("exit", (code) => (code === 0 ? resolve() : reject(new Error(`${file} exited ${code}`))));
  });
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
