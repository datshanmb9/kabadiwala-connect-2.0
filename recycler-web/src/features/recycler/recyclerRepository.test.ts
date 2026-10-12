import { describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../../api/apiClient'
import { RecyclerRepository } from './recyclerRepository'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

describe('RecyclerRepository.register', () => {
  it('sends the exact registration request body the backend expects', async () => {
    let capturedBody: unknown
    const fetchImpl = vi.fn().mockImplementation((url: string, init: RequestInit) => {
      expect(url).toContain('/api/v1/recyclers/register')
      capturedBody = JSON.parse(init.body as string)
      return Promise.resolve(
        jsonResponse({
          user_id: 'recycler-1', username: 'demo-recycler-1', license_id: 'demo-recycler-1',
          company_name: 'Demo Co', status: 'PENDING',
        }),
      )
    })
    const repo = new RecyclerRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    const profile = await repo.register({ username: 'demo-recycler-1', password: 'recyclerpass123', companyName: 'Demo Co' })

    expect(capturedBody).toEqual({ username: 'demo-recycler-1', password: 'recyclerpass123', company_name: 'Demo Co' })
    expect(profile.status).toBe('PENDING')
  })

  it('propagates USERNAME_ALREADY_EXISTS as a structured error', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ success: false, error_code: 'USERNAME_ALREADY_EXISTS', message: 'Taken.' }, 409),
      )
    const repo = new RecyclerRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    await expect(
      repo.register({ username: 'demo-recycler-1', password: 'x', companyName: 'x' }),
    ).rejects.toMatchObject({ errorCode: 'USERNAME_ALREADY_EXISTS' })
  })
})

describe('RecyclerRepository.getProfile', () => {
  it('attaches the bearer token', async () => {
    const fetchImpl = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const headers = init.headers as Record<string, string>
      expect(headers.Authorization).toBe('Bearer tok-1')
      return Promise.resolve(
        jsonResponse({
          user_id: 'recycler-1', username: 'demo-recycler-1', license_id: 'demo-recycler-1',
          company_name: 'Demo Co', status: 'APPROVED',
        }),
      )
    })
    const repo = new RecyclerRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    const profile = await repo.getProfile('tok-1')
    expect(profile.status).toBe('APPROVED')
  })
})
