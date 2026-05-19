const SENSITIVE_KEYS = new Set([
  "signing_private_key",
  "private_key",
  "privateKey",
  "secret",
  "api_key",
  "apiKey"
]);

export function redactSensitive(value) {
  if (Array.isArray(value)) {
    return value.map((item) => redactSensitive(item));
  }

  if (!value || typeof value !== "object") {
    return value;
  }

  const redacted = {};
  for (const [key, item] of Object.entries(value)) {
    if (SENSITIVE_KEYS.has(key)) continue;
    redacted[key] = redactSensitive(item);
  }
  return redacted;
}

export function publicUser(user) {
  if (!user) return null;
  return redactSensitive(user);
}
