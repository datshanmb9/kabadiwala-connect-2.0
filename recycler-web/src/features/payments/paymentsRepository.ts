import { ApiClient, apiClient as defaultApiClient } from '../../api/apiClient'
import type { Payment } from '../../types/domain'

export class PaymentsRepository {
  private readonly client: ApiClient
  constructor(client: ApiClient = defaultApiClient) {
    this.client = client
  }

  /** Never sends or receives any provider credential — the request
   * carries only the lot id; the backend derives the amount from the
   * already-accepted bid. */
  async initiatePayment(lotId: string, accessToken: string, idempotencyKey: string): Promise<Payment> {
    return this.client.post(`/api/v1/payments/${lotId}/initiate`, undefined, accessToken, idempotencyKey)
  }

  async listPaymentsForLot(lotId: string, accessToken: string): Promise<Payment[]> {
    const res = await this.client.get<{ success: true; payments: Payment[] }>(
      `/api/v1/payments/lot/${lotId}`,
      accessToken,
    )
    return res.payments
  }
}

export const paymentsRepository = new PaymentsRepository()
