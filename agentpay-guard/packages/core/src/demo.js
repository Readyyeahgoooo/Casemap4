export function seedScenario(guard, scenario) {
  const principal = guard.createPrincipal(scenario.principal);
  const user = guard.createUser({ ...scenario.user, principal_id: principal.id });
  const agent = guard.createAgent({ ...scenario.agent, principal_id: principal.id });
  const mandate = guard.createMandate({
    ...scenario.mandate,
    agent_id: agent.id,
    principal_id: principal.id,
    signed_by: scenario.mandate.signed_by ?? user.email
  });

  return { principal, user, agent, mandate };
}

export function runScenario(guard, scenario, actor = "demo") {
  const seeded = seedScenario(guard, scenario);
  const paymentRequest = {
    ...scenario.payment_request,
    agent_id: seeded.agent.id,
    mandate_id: seeded.mandate.id
  };

  const result = guard.checkPayment(paymentRequest, actor);
  const execution =
    result.decision.status === "approved"
      ? guard.executeMockPayment(result.payment_request.id, actor)
      : null;

  return {
    seeded,
    result,
    execution,
    evidence_pack: guard.exportEvidencePack(result.payment_request.id)
  };
}
