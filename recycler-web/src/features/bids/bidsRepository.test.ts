import { describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../../api/apiClient'
import { BidsRepository } from './bidsRepository'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

describe('BidsRepository.placeBid', () => {
  it('sends the amount as a decimal STRING, with Idempotency-Key', async () => {
    let capturedBody: unknown
    const fetchImpl = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      expect(url).toContain('/api/v1/bids')
      const headers = init.headers as Record<string, string>
      expect(headers['Idempotency-Key']).toBe('idem-1')
      capturedBody = JSON.parse(init.body as string)
      return Promise.resolve(
        jsonResponse({
          bid_id: 'bid-1', lot_id: 'lot-1', recycler_id: 'demo-recycler-1', amount: '1250.50',
          status: 'PLACED', placed_at: '2026-09-14T00:00:00', accepted_at: null,
        }),
      )
    })
    const repo = new BidsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    const bid = await repo.placeBid('lot-1', '1250.50', 'tok-1', 'idem-1')

    expect(capturedBody).toEqual({ lot_id: 'lot-1', amount: '1250.50' })
    expect(typeof capturedBody === 'object' && capturedBody !== null && 'amount' in capturedBody).toBe(true)
    expect(typeof (capturedBody as { amount: unknown }).amount).toBe('string')
    expect(bid.amount).toBe('1250.50')
  });

  it('a retry with the SAME idempotency key sends the same key value again', async () => {
    const sentKeys: (string | undefined)[] = []
    const fetchImpl = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const headers = init.headers as Record<string, string>
      sentKeys.push(headers['Idempotency-Key'])
      return Promise.resolve(
        jsonResponse({
          bid_id: 'bid-1', lot_id: 'lot-1', recycler_id: 'demo-recycler-1', amount: '100',
          status: 'PLACED', placed_at: '2026-09-14T00:00:00', accepted_at: null,
        }),
      )
    })
    const repo = new BidsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const key = 'fixed-retry-key'
    await repo.placeBid('lot-1', '100', 'tok-1', key)
    await repo.placeBid('lot-1', '100', 'tok-1', key)
    expect(sentKeys).toEqual([key, key])
  })

  it('propagates INVALID_BID_AMOUNT as a structured error', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ success: false, error_code: 'INVALID_BID_AMOUNT', message: 'Bad amount.' }, 400),
      )
    const repo = new BidsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    await expect(repo.placeBid('lot-1', '-5', 'tok-1', 'idem-1')).rejects.toMatchObject({
      errorCode: 'INVALID_BID_AMOUNT',
    })
  })
})

describe('BidsRepository.cancelBid', () => {
  it('posts to the cancel path', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      expect(url).toContain('/api/v1/bids/bid-1/cancel')
      return Promise.resolve(
        jsonResponse({
          bid_id: 'bid-1', lot_id: 'lot-1', recycler_id: 'demo-recycler-1', amount: '100',
          status: 'CANCELLED', placed_at: '2026-09-14T00:00:00', accepted_at: null,
        }),
      )
    })
    const repo = new BidsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const bid = await repo.cancelBid('bid-1', 'tok-1', 'idem-1')
    expect(bid.status).toBe('CANCELLED')
  })
})

describe('BidsRepository.listMyBids', () => {
  it('parses the bids list', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ success: true, bids: [] }))
    const repo = new BidsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    expect(await repo.listMyBids('tok-1')).toEqual([])
  })
})
