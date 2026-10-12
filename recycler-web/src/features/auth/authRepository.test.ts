import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../../api/apiClient'
import { AuthRepository, WrongRoleError } from './authRepository'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

beforeEach(() => {
  localStorage.clear()
})

describe('AuthRepository.login', () => {
  it('on success, fetches /me and persists the combined session', async () => {
    const storage = 'kc_recycler_auth_session'
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/auth/login')) {
        return Promise.resolve(
          jsonResponse({ access_token: 'acc-1', refresh_token: 'ref-1', role: 'RECYCLER' }),
        )
      }
      return Promise.resolve(jsonResponse({ user_id: 'recycler-1', username: 'demo-recycler-1', role: 'RECYCLER' }))
    })
    const repo = new AuthRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    const session = await repo.login('demo-recycler-1', 'password123')

    expect(session.accessToken).toBe('acc-1')
    expect(session.username).toBe('demo-recycler-1')
    expect(localStorage.getItem(storage)).toContain('acc-1')
  })

  it('rejects a non-RECYCLER role without persisting a session', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse({ access_token: 'acc-1', refresh_token: 'ref-1', role: 'RRR_CENTER' }))
    const repo = new AuthRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    await expect(repo.login('rrr-1', 'password123')).rejects.toBeInstanceOf(WrongRoleError)
    expect(localStorage.getItem('kc_recycler_auth_session')).toBeNull()
  })

  it('propagates invalid-credentials errors from the backend', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ success: false, error_code: 'INVALID_CREDENTIALS', message: 'Invalid username or password.' }, 401),
      )
    const repo = new AuthRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    await expect(repo.login('recycler-1', 'wrong')).rejects.toMatchObject({ errorCode: 'INVALID_CREDENTIALS' })
  })
})

describe('AuthRepository.restoreSession', () => {
  it('returns null when nothing is stored', async () => {
    const repo = new AuthRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl: vi.fn() }))
    expect(await repo.restoreSession()).toBeNull()
  })

  it('an expired access token is refreshed via /auth/refresh, then /me', async () => {
    localStorage.setItem(
      'kc_recycler_auth_session',
      JSON.stringify({
        accessToken: 'stale-acc', refreshToken: 'stale-ref', role: 'RECYCLER', userId: 'recycler-1', username: 'demo-recycler-1',
      }),
    )
    let refreshCalled = false
    const fetchImpl = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/auth/me') && !refreshCalled) {
        return Promise.resolve(jsonResponse({ success: false, error_code: 'INVALID_TOKEN', message: 'Invalid.' }, 401))
      }
      if (url.includes('/api/v1/auth/refresh')) {
        refreshCalled = true
        return Promise.resolve(jsonResponse({ access_token: 'new-acc' }))
      }
      return Promise.resolve(jsonResponse({ user_id: 'recycler-1', username: 'demo-recycler-1', role: 'RECYCLER' }))
    })
    const repo = new AuthRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    const session = await repo.restoreSession()
    expect(session?.accessToken).toBe('new-acc')
  })

  it('when refresh also fails, storage is cleared and null is returned', async () => {
    localStorage.setItem(
      'kc_recycler_auth_session',
      JSON.stringify({
        accessToken: 'stale-acc', refreshToken: 'stale-ref', role: 'RECYCLER', userId: 'recycler-1', username: 'demo-recycler-1',
      }),
    )
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse({ success: false, error_code: 'INVALID_TOKEN', message: 'Invalid.' }, 401))
    const repo = new AuthRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    const session = await repo.restoreSession()
    expect(session).toBeNull()
    expect(localStorage.getItem('kc_recycler_auth_session')).toBeNull()
  })
})

describe('AuthRepository.logout', () => {
  it('clears local storage even if the server call fails', async () => {
    const stubSession = {
      accessToken: 'acc', refreshToken: 'ref', role: 'RECYCLER', userId: 'recycler-1', username: 'demo-recycler-1',
    }
    localStorage.setItem('kc_recycler_auth_session', JSON.stringify(stubSession))
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse({ success: false, error_code: 'INVALID_TOKEN', message: 'x' }, 401))
    const repo = new AuthRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))

    await repo.logout(stubSession)
    expect(localStorage.getItem('kc_recycler_auth_session')).toBeNull()
  })
})
