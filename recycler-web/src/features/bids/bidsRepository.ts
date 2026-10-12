import { ApiClient, apiClient as defaultApiClient } from '../../api/apiClient'
import type { Bid } from '../../types/domain'

export class BidsRepository {
  private readonly client: ApiClient
  constructor(client: ApiClient = defaultApiClient) {
    this.client = client
  }

  /** amount is sent as a decimal STRING, never a JS number/float, so the
   * client can't introduce binary-float rounding before the server even
   * sees it — the backend parses it to Decimal and stores Decimal128. */
  async placeBid(lotId: string, amount: string, accessToken: string, idempotencyKey: string): Promise<Bid> {
    return this.client.post('/api/v1/bids', { lot_id: lotId, amount }, accessToken, idempotencyKey)
  }

  async cancelBid(bidId: string, accessToken: string, idempotencyKey: string): Promise<Bid> {
    return this.client.post(`/api/v1/bids/${bidId}/cancel`, undefined, accessToken, idempotencyKey)
  }

  async listMyBids(accessToken: string): Promise<Bid[]> {
    const json = await this.client.get<{ bids: Bid[] }>('/api/v1/bids/mine', accessToken)
    return json.bids ?? []
  }
}

export const bidsRepository = new BidsRepository()
