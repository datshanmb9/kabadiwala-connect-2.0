import { ApiClient, apiClient as defaultApiClient } from '../../api/apiClient'
import type { Lot } from '../../types/domain'

export class LotsRepository {
  private readonly client: ApiClient
  constructor(client: ApiClient = defaultApiClient) {
    this.client = client
  }

  /** Marketplace-wide — every lot currently open for bidding, across all
   * RRRs/wards. Recyclers are not ward-scoped anywhere in the architecture. */
  async listListedForBidding(accessToken: string): Promise<Lot[]> {
    const json = await this.client.get<{ lots: Lot[] }>('/api/v1/lots/listed', accessToken)
    return json.lots ?? []
  }

  async getLot(lotId: string, accessToken: string): Promise<Lot> {
    return this.client.get<Lot>(`/api/v1/lots/${lotId}`, accessToken)
  }
}

export const lotsRepository = new LotsRepository()
