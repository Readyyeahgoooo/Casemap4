#!/usr/bin/env node
import { readFile } from "node:fs/promises";

const [, , taskPath] = process.argv;
const apiKey = process.env.DEEPSEEK_API_KEY;
const model = process.env.DEEPSEEK_MODEL ?? "deepseek-v4-pro";
const baseUrl = process.env.DEEPSEEK_BASE_URL ?? "https://api.deepseek.com";

if (!taskPath) {
  console.error("Usage: DEEPSEEK_API_KEY=... node scripts/deepseek-worker.mjs prompts/deepseek/<task>.md");
  process.exit(1);
}

if (!apiKey) {
  console.error("DEEPSEEK_API_KEY is required. Use a rotated key; never hard-code it in repo files.");
  process.exit(1);
}

const task = await readFile(taskPath, "utf8");

const response = await fetch(`${baseUrl}/chat/completions`, {
  method: "POST",
  headers: {
    "content-type": "application/json",
    authorization: `Bearer ${apiKey}`
  },
  body: JSON.stringify({
    model,
    temperature: 0.2,
    messages: [
      {
        role: "system",
        content:
          "You are DeepSeek-V4-Pro acting as a disciplined implementation worker. Return concise, patch-oriented guidance. Do not claim compliance, do not invent regulatory approvals, and do not request secrets."
      },
      {
        role: "user",
        content: task
      }
    ]
  })
});

if (!response.ok) {
  const errorText = await response.text();
  console.error(`DeepSeek API error ${response.status}: ${errorText}`);
  process.exit(1);
}

const payload = await response.json();
const content = payload.choices?.[0]?.message?.content ?? "";
console.log(content);
