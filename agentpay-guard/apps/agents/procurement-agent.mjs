#!/usr/bin/env node
import { runAgentLoop } from "./lib/run-agent.js";

const once = process.argv.includes("--once");
const intervalFlag = process.argv.find((arg) => arg.startsWith("--interval="));
const intervalMs = intervalFlag ? Number(intervalFlag.split("=")[1]) : Number(process.env.AGENTPAY_AGENT_INTERVAL_MS ?? 12_000);

await runAgentLoop("procurement", { intervalMs, once });
