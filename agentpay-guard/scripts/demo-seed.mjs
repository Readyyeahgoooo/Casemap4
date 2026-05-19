#!/usr/bin/env node
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { apiRequest } from "../apps/agents/lib/api-client.js";

const world = await apiRequest("/demo/seed-agents", { method: "POST" });
const outPath = path.resolve(process.cwd(), "data/demo-agents-registry.json");
await writeFile(outPath, `${JSON.stringify(world, null, 2)}\n`, "utf8");

console.log("Demo agents seeded.");
console.log(`Registry written to ${outPath}`);
for (const agent of world.agents) {
  console.log(`- ${agent.slug}: ${agent.name} (${agent.agent_id})`);
}
