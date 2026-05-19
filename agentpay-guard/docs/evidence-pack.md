# Evidence Pack

`exportEvidencePack(payment_request_id)` returns the audit artefact for a payment authority decision. It is a KYA-lite authority evidence file, not a full KYC/KYB or AML audit.

## Fields

- `evidence_pack_version`: evidence schema version.
- `exported_at`: export timestamp.
- `principal`: company/controller record entered into the system.
- `approver_user`: active user under the principal whose email matched `mandate.signed_by`.
- `agent`: AI-agent identity record.
- `mandate`: authority scope, allowlists, denylists, thresholds, expiry, signer, and placeholder signature.
- `payment_request`: normalized payment request, including idempotency key, decision TTL, and request hash.
- `decision`: deterministic policy result, reason, checked rules, triggered rules, and policy version.
- `payment`: mock payment execution record when the decision was approved.
- `receipt`: payment authority receipt when execution occurred.
- `case`: review case for blocked, manual-review, or pending-human-approval outcomes.
- `authority_chain_summary`: compact IDs for principal -> approver -> agent -> mandate -> request -> decision -> receipt/case.
- `audit_events`: full hash-chained audit log.
- `scoped_audit_events`: reviewer-friendly subset related to this evidence pack.
- `audit_verification`: hash-chain verification result.

## Honest Scope

The evidence pack can show that an agent was linked to a principal, signed under a mandate, checked against deterministic payment rules, and recorded with an audit chain. It does not prove real-world company existence, sanctions clearance, legal authorisation, or regulatory compliance.
