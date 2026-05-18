import { sha256 } from "../../shared/src/hash.js";

export function createAuditEvent({
  id,
  type,
  actor = "system",
  subject_id,
  case_id = null,
  input = {},
  output = {},
  policy_version = null,
  previous_event_hash = null,
  created_at = new Date().toISOString()
}) {
  const input_hash = sha256(input);
  const output_hash = sha256(output);
  const eventForHash = {
    id,
    type,
    actor,
    subject_id,
    case_id,
    input_hash,
    output_hash,
    policy_version,
    previous_event_hash,
    created_at
  };

  return {
    ...eventForHash,
    event_hash: sha256(eventForHash)
  };
}

export function verifyAuditChain(events) {
  let previous = null;
  const failures = [];

  for (const event of events) {
    if (event.previous_event_hash !== previous) {
      failures.push({
        event_id: event.id,
        reason: "previous_event_hash_mismatch",
        expected: previous,
        actual: event.previous_event_hash
      });
    }

    const recalculated = sha256({
      id: event.id,
      type: event.type,
      actor: event.actor,
      subject_id: event.subject_id,
      case_id: event.case_id,
      input_hash: event.input_hash,
      output_hash: event.output_hash,
      policy_version: event.policy_version,
      previous_event_hash: event.previous_event_hash,
      created_at: event.created_at
    });

    if (recalculated !== event.event_hash) {
      failures.push({
        event_id: event.id,
        reason: "event_hash_mismatch",
        expected: recalculated,
        actual: event.event_hash
      });
    }

    previous = event.event_hash;
  }

  return {
    valid: failures.length === 0,
    failures
  };
}
