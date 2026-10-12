import { describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../../api/apiClient'
import { LotsRepository } from './lotsRepository'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

describe('LotsRepository.listListedForBidding', () => {
  it('requests the marketplace-wide path and attaches the bearer token', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      expect(url).toContain('/api/v1/lots/listed')
      const headers = init.headers as Record<string, string>
      expect(headers.Authorization).toBe('Bearer tok-1')
      return Promise.resolve(
        jsonResponse({
          success: true,
          lots: [
            { lot_id: 'lot-1', rrr_id: 'RRR-1', ward_id: 'WARD-1', category: 'metal-scrap', item_ids: ['a'], status: 'LISTED_FOR_BIDDING', bid_deadline: null },
          ],
        }),
      )
    })
    const repo = new LotsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    const lots = await repo.listListedForBidding('tok-1')
    expect(lots).toHaveLength(1)
    expect(lots[0].lot_id).toBe('lot-1')
  })

  it('propagates RECYCLER_NOT_APPROVED as a structured error', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ success: false, error_code: 'RECYCLER_NOT_APPROVED', message: 'Not approved.' }, 403),
      )
    const repo = new LotsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    await expect(repo.listListedForBidding('tok-1')).rejects.toMatchObject({ errorCode: 'RECYCLER_NOT_APPROVED' })
  })
})

describe('LotsRepository.getLot', () => {
  it('requests the correct path and parses the response', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      expect(url).toContain('/api/v1/lots/lot-1')
      return Promise.resolve(
        jsonResponse({
          lot_id: 'lot-1', rrr_id: 'RRR-1', ward_id: 'WARD-1', category: 'metal-scrap', item_ids: ['a'],
          status: 'LISTED_FOR_BIDDING', bid_deadline: '2026-09-21T00:00:00Z',
        }),
      )
    })
    const repo = new LotsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    const lot = await repo.getLot('lot-1', 'tok-1')
    expect(lot.status).toBe('LISTED_FOR_BIDDING')
  })
})
