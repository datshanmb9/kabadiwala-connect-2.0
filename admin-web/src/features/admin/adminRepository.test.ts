import { describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../../api/apiClient'
import { AdminRepository } from './adminRepository'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

describe('AdminRepository.getDashboardSummary', () => {
  it('unwraps the summary object and attaches the bearer token', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      expect(url).toContain('/api/v1/admin/dashboard/summary')
      const headers = init.headers as Record<string, string>
      expect(headers.Authorization).toBe('Bearer tok-1')
      return Promise.resolve(
        jsonResponse({ success: true, summary: { users_by_role: { HOME_USER: 2 }, wards_count: 1 } }),
      )
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const summary = await repo.getDashboardSummary('tok-1')
    expect(summary.wards_count).toBe(1)
  })
})

describe('AdminRepository RRR centre approvals', () => {
  it('lists RRR centres with an optional status filter in the query string', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      expect(url).toContain('/api/v1/admin/rrr-centres?status=PENDING')
      return Promise.resolve(jsonResponse({ success: true, rrr_centres: [] }))
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await repo.listRrrCentres('tok-1', 'PENDING')
  })

  it('approves an RRR centre via POST to the approve path', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      expect(url).toContain('/api/v1/admin/rrr-centres/user-1/approve')
      return Promise.resolve(
        jsonResponse({ user_id: 'user-1', username: 'rrr-1', rrr_id: 'RRR-1', tender_id: 'T-1', ward_id: 'WARD-1', licence_doc_ref: null, status: 'APPROVED' }),
      )
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const result = await repo.approveRrrCentre('user-1', 'tok-1')
    expect(result.status).toBe('APPROVED')
  })
})

describe('AdminRepository recycler approvals', () => {
  it('propagates RECYCLER_NOT_PENDING as a structured error', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse({ success: false, error_code: 'RECYCLER_NOT_PENDING', message: 'x' }, 400))
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await expect(repo.approveRecycler('user-1', 'tok-1')).rejects.toMatchObject({ errorCode: 'RECYCLER_NOT_PENDING' })
  })
})

describe('AdminRepository collector management', () => {
  it('creates a collector with the exact request body the backend expects', async () => {
    let capturedBody: unknown
    const fetchImpl = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      expect(url).toContain('/api/v1/admin/collectors')
      capturedBody = JSON.parse(init.body as string)
      return Promise.resolve(
        jsonResponse({ user_id: 'u1', employee_id: 'EMP-1', ward_id: 'WARD-1', rrr_id: null, assigned_area_radius_m: null }),
      )
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await repo.createCollector({ employeeId: 'EMP-1', password: 'pass1234', wardId: 'WARD-1' }, 'tok-1')
    expect(capturedBody).toEqual({ employee_id: 'EMP-1', password: 'pass1234', ward_id: 'WARD-1', rrr_id: null, assigned_area_radius_m: null })
  })

  it('updates a collector assignment via PATCH and unwraps the response', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      expect(url).toContain('/api/v1/admin/collectors/u1')
      expect(init.method).toBe('PATCH')
      return Promise.resolve(
        jsonResponse({ success: true, collector: { user_id: 'u1', employee_id: 'EMP-1', ward_id: 'WARD-2', rrr_id: null, assigned_area_radius_m: null, status: 'ACTIVE' } }),
      )
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const collector = await repo.updateCollectorAssignment('u1', { wardId: 'WARD-2' }, 'tok-1')
    expect(collector.ward_id).toBe('WARD-2')
  })

  it('sets collector status and unwraps the response', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      expect(url).toContain('/api/v1/admin/collectors/u1/status')
      return Promise.resolve(
        jsonResponse({ success: true, collector: { user_id: 'u1', employee_id: 'EMP-1', ward_id: 'WARD-1', rrr_id: null, assigned_area_radius_m: null, status: 'DISABLED' } }),
      )
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const collector = await repo.setCollectorStatus('u1', 'DISABLED', 'tok-1')
    expect(collector.status).toBe('DISABLED')
  })
})

describe('AdminRepository wards', () => {
  it('lists wards (public endpoint contract, but repository always attaches the token it is given)', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ success: true, wards: [{ ward_id: 'WARD-1', name: 'Ward 1' }] }))
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const wards = await repo.listWards('tok-1')
    expect(wards).toHaveLength(1)
  })
})

describe('AdminRepository oversight lists', () => {
  it('lists submissions with a status filter', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      expect(url).toContain('status=FLAGGED_FOR_REVIEW')
      return Promise.resolve(jsonResponse({ success: true, submissions: [] }))
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await repo.listSubmissions('tok-1', 'FLAGGED_FOR_REVIEW')
  })

  it('lists lots without a filter when status is omitted', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      expect(url).not.toContain('?')
      return Promise.resolve(jsonResponse({ success: true, lots: [] }))
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await repo.listLots('tok-1')
  })

  it('lists bids', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ success: true, bids: [] }))
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    expect(await repo.listBids('tok-1')).toEqual([])
  })
})

describe('AdminRepository complaints', () => {
  it('reviews a complaint with the exact request body', async () => {
    let capturedBody: unknown
    const fetchImpl = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      expect(url).toContain('/api/v1/admin/complaints/c1/review')
      capturedBody = JSON.parse(init.body as string)
      return Promise.resolve(
        jsonResponse({ complaint_id: 'c1', reporter_id: 'r1', reporter_role: 'COLLECTOR', target_type: 'ward', target_id: 'WARD-1', category: 'X', description: 'y', status: 'IN_PROGRESS', resolution_notes: null, created_at: '2026-01-01T00:00:00' }),
      )
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const complaint = await repo.reviewComplaint('c1', 'IN_PROGRESS', 'tok-1')
    expect(complaint.status).toBe('IN_PROGRESS')
    expect(capturedBody).toEqual({ new_status: 'IN_PROGRESS', resolution_notes: undefined })
  })
})

describe('AdminRepository payments oversight', () => {
  it('lists payments with an optional status filter', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      expect(url).toContain('/api/v1/admin/payments?status=SUCCEEDED')
      return Promise.resolve(jsonResponse({ success: true, payments: [] }))
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await repo.listPayments('tok-1', 'SUCCEEDED')
  })
})

describe('AdminRepository rewards', () => {
  it('computes rewards for a period and unwraps the created list', async () => {
    let capturedBody: unknown
    const fetchImpl = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      expect(url).toContain('/api/v1/admin/rewards/compute')
      capturedBody = JSON.parse(init.body as string)
      return Promise.resolve(
        jsonResponse({
          success: true,
          created: [{ reward_id: 'r1', home_user_id: 'h1', period: '2026-09', points: 10, amount: '5.00', status: 'CREDITED', created_at: '2026-09-01T00:00:00' }],
          count: 1,
        }),
      )
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    const created = await repo.computeRewards('2026-09', 'tok-1')
    expect(capturedBody).toEqual({ period: '2026-09' })
    expect(created).toHaveLength(1)
    expect(created[0].amount).toBe('5.00')
  })

  it('lists rewards with an optional period filter', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      expect(url).toContain('/api/v1/admin/rewards?period=2026-09')
      return Promise.resolve(jsonResponse({ success: true, rewards: [] }))
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await repo.listRewards('tok-1', '2026-09')
  })

  it('propagates INVALID_PERIOD as a structured error', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse({ success: false, error_code: 'INVALID_PERIOD', message: 'x' }, 400))
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await expect(repo.computeRewards('not-a-period', 'tok-1')).rejects.toMatchObject({ errorCode: 'INVALID_PERIOD' })
  })
})

describe('AdminRepository audit logs', () => {
  it('applies actorRole/entityType filters in the query string', async () => {
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      expect(url).toContain('actor_role=GOVERNMENT_ADMIN')
      expect(url).toContain('entity_type=collector')
      return Promise.resolve(jsonResponse({ success: true, logs: [] }))
    })
    const repo = new AdminRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
    await repo.listAuditLogs('tok-1', { actorRole: 'GOVERNMENT_ADMIN', entityType: 'collector' })
  })
})
