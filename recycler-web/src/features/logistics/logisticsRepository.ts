import { ApiClient, apiClient as defaultApiClient } from '../../api/apiClient'
import type { LogisticsBooking } from '../../types/domain'

export class LogisticsRepository {
  private readonly client: ApiClient
  constructor(client: ApiClient = defaultApiClient) {
    this.client = client
  }

  async bookLogistics(
    lotId: string,
    slotTime: string,
    accessToken: string,
    idempotencyKey: string,
  ): Promise<LogisticsBooking> {
    return this.client.post(`/api/v1/logistics/${lotId}/book`, { slot_time: slotTime }, accessToken, idempotencyKey)
  }

  async confirmCollection(
    bookingId: string,
    accessToken: string,
    idempotencyKey: string,
  ): Promise<LogisticsBooking> {
    return this.client.post(`/api/v1/logistics/${bookingId}/confirm-collection`, undefined, accessToken, idempotencyKey)
  }

  /** Returns null if this lot has no booking yet, or if the caller
   * doesn't own its accepted bid (the backend's ownership check is
   * what actually enforces this — a 403 here just means "nothing to
   * show", not an app error). */
  async getBookingForLot(lotId: string, accessToken: string): Promise<LogisticsBooking | null> {
    const res = await this.client.get<{ success: true; booking: LogisticsBooking | null }>(
      `/api/v1/logistics/lot/${lotId}`,
      accessToken,
    )
    return res.booking
  }
}

export const logisticsRepository = new LogisticsRepository()
