import { AgentPayGuard as CoreGuard } from "../../core/src/index.js";

export class AgentPayGuard {
  constructor(options = {}) {
    this.core = options.core ?? new CoreGuard(options);
  }

  createPrincipal(input) {
    return this.core.createPrincipal(input, input.actor);
  }

  createUser(input) {
    return this.core.createUser(input, input.actor);
  }

  createAgent(input) {
    return this.core.createAgent(input, input.actor);
  }

  createMandate(input) {
    return this.core.createMandate(input, input.actor);
  }

  checkPayment(input) {
    return this.core.checkPayment(input, input.actor);
  }

  executeMockPayment(paymentRequestId, actor = "system") {
    return this.core.executeMockPayment(paymentRequestId, actor);
  }

  revokeMandate(mandateId, actor = "system") {
    return this.core.revokeMandate(mandateId, actor);
  }

  getReceipt(receiptId) {
    return this.core.getReceipt(receiptId);
  }

  exportEvidencePack(paymentRequestId) {
    return this.core.exportEvidencePack(paymentRequestId);
  }
}
