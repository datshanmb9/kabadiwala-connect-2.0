import { describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../../api/apiClient'
import { PaymentsRepository } from './paymentsRepository'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

describe('PaymentsRepository.initiatePayment', () => {
  it('posts to the correct path with Idempotency-Key and no body (amount is never client-supplied)', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      expect(url).toContain('/api/v1/payments/lot-1/initiate')
      const headers = init.headers as Record<string, string>
      expect(headers['Idempotency-Key']).toBe('idem-1')
      expect(init.body).toBeUndefined()
      return Promise.resolve(
        jsonResponse({
          payment_id: 'pay-1', lot_id: 'lot-1', recycler_id: 'demo-recycler-1', amount: '500.00',
          status: 'SUCCEEDED', gateway: 'MOCK_PAYMENT_GATEWAY', gateway_reference: 'MOCK-abc123',
          created_at: '2026-10-01T10:00:00',
        }),
      )
    })
    const repo = new PaymentsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    const payment = await repo.initiatePayment('lot-1', 'tok-1', 'idem-1')
    expect(payment.status).toBe('SUCCEEDED')
    expect(typeof payment.amount).toBe('string')
  })

  it('surfaces a FAILED result without throwing (a failed payment is not an app error)', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse({
        payment_id: 'pay-2', lot_id: 'lot-1', recycler_id: 'demo-recycler-1', amount: '100.00',
        status: 'FAILED', gateway: 'MOCK_PAYMENT_GATEWAY', gateway_reference: 'MOCK-def456',
        created_at: '2026-10-01T10:00:00',
      }),
    )
    const repo = new PaymentsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const payment = await repo.initiatePayment('lot-1', 'tok-1', 'idem-2')
    expect(payment.status).toBe('FAILED')
  })

  it('propagates LOT_ALREADY_PAID as a structured error', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse({ success: false, error_code: 'LOT_ALREADY_PAID', message: 'x' }, 409))
    const repo = new PaymentsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await expect(repo.initiatePayment('lot-1', 'tok-1', 'idem-3')).rejects.toMatchObject({
      errorCode: 'LOT_ALREADY_PAID',
    })
  })

  it('never sends any credential/secret field in the request', async () => {
    const fetchImpl = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      expect(init.body).toBeUndefined()
      return Promise.resolve(
        jsonResponse({
          payment_id: 'pay-1', lot_id: 'lot-1', recycler_id: 'demo-recycler-1', amount: '500.00',
          status: 'SUCCEEDED', gateway: 'MOCK_PAYMENT_GATEWAY', gateway_reference: 'MOCK-abc123',
          created_at: '2026-10-01T10:00:00',
        }),
      )
    })
    const repo = new PaymentsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await repo.initiatePayment('lot-1', 'tok-1', 'idem-4')
  })
})

describe('PaymentsRepository.listPaymentsForLot', () => {
  it('lists the append-only payment history for a lot', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse({
        success: true,
        payments: [
          { payment_id: 'p1', lot_id: 'lot-1', recycler_id: 'r1', amount: '100.00', status: 'FAILED', gateway: 'MOCK_PAYMENT_GATEWAY', gateway_reference: 'MOCK-1', created_at: '2026-10-01T09:00:00' },
          { payment_id: 'p2', lot_id: 'lot-1', recycler_id: 'r1', amount: '100.00', status: 'SUCCEEDED', gateway: 'MOCK_PAYMENT_GATEWAY', gateway_reference: 'MOCK-2', created_at: '2026-10-01T10:00:00' },
        ],
      }),
    )
    const repo = new PaymentsRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const payments = await repo.listPaymentsForLot('lot-1', 'tok-1')
    expect(payments).toHaveLength(2)
  })
})
