import { describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../../api/apiClient'
import { LogisticsRepository } from './logisticsRepository'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

describe('LogisticsRepository.bookLogistics', () => {
  it('posts the slot_time and Idempotency-Key to the correct path', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      expect(url).toContain('/api/v1/logistics/lot-1/book')
      const headers = init.headers as Record<string, string>
      expect(headers['Idempotency-Key']).toBe('idem-1')
      expect(JSON.parse(init.body as string)).toEqual({ slot_time: '2026-10-01T10:00:00.000Z' })
      return Promise.resolve(
        jsonResponse({
          booking_id: 'booking-1', lot_id: 'lot-1', recycler_id: 'demo-recycler-1',
          slot_time: '2026-10-01T10:00:00.000Z', status: 'BOOKED',
        }),
      )
    })
    const repo = new LogisticsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    const booking = await repo.bookLogistics('lot-1', '2026-10-01T10:00:00.000Z', 'tok-1', 'idem-1')
    expect(booking.status).toBe('BOOKED')
  })

  it('propagates LOT_NOT_BID_SELECTED as a structured error', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse({ success: false, error_code: 'LOT_NOT_BID_SELECTED', message: 'x' }, 400))
    const repo = new LogisticsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    await expect(repo.bookLogistics('lot-1', '2026-10-01T10:00:00.000Z', 'tok-1', 'idem-1')).rejects.toMatchObject({
      errorCode: 'LOT_NOT_BID_SELECTED',
    })
  })
})

describe('LogisticsRepository.confirmCollection', () => {
  it('posts to the confirm-collection path', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      expect(url).toContain('/api/v1/logistics/booking-1/confirm-collection')
      return Promise.resolve(
        jsonResponse({
          booking_id: 'booking-1', lot_id: 'lot-1', recycler_id: 'demo-recycler-1',
          slot_time: '2026-10-01T10:00:00.000Z', status: 'COLLECTED',
        }),
      )
    })
    const repo = new LogisticsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const booking = await repo.confirmCollection('booking-1', 'tok-1', 'idem-2')
    expect(booking.status).toBe('COLLECTED')
  })
})

describe('LogisticsRepository.getBookingForLot', () => {
  it('returns the booking when one exists', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse({
        success: true,
        booking: { booking_id: 'booking-1', lot_id: 'lot-1', recycler_id: 'demo-recycler-1', slot_time: '2026-10-01T10:00:00.000Z', status: 'BOOKED' },
      }),
    )
    const repo = new LogisticsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const booking = await repo.getBookingForLot('lot-1', 'tok-1')
    expect(booking?.booking_id).toBe('booking-1')
  })

  it('returns null when no booking exists yet', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ success: true, booking: null }))
    const repo = new LogisticsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    expect(await repo.getBookingForLot('lot-1', 'tok-1')).toBeNull()
  })

  it('propagates NOT_ACCEPTED_BID_OWNER as a structured error (the page treats this as "nothing to show")', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse({ success: false, error_code: 'NOT_ACCEPTED_BID_OWNER', message: 'x' }, 403))
    const repo = new LogisticsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await expect(repo.getBookingForLot('lot-1', 'tok-1')).rejects.toMatchObject({ errorCode: 'NOT_ACCEPTED_BID_OWNER' })
  })
})
