import { ApiClient, ApiError, apiClient as defaultApiClient } from '../../api/apiClient'
import type { AuthSession } from '../../types/domain'

/** This app is RECYCLER-only — refused client-side even though backend
 * RBAC is the actual boundary, same principle as rrr-centre-web. */
export class WrongRoleError extends Error {
  readonly role: string
  constructor(role: string) {
    super(`Unsupported role: ${role}`)
    this.role = role
  }
}

const SESSION_STORAGE_KEY = 'kc_recycler_auth_session'

export class AuthRepository {
  private readonly client: ApiClient
  constructor(client: ApiClient = defaultApiClient) {
    this.client = client
  }

  async login(username: string, password: string): Promise<AuthSession> {
    const tokenJson = await this.client.post<{ access_token: string; refresh_token: string; role: string }>(
      '/api/v1/auth/login',
      { username, password },
    )
    if (tokenJson.role !== 'RECYCLER') {
      throw new WrongRoleError(tokenJson.role)
    }

    const me = await this.client.get<{ user_id: string; username: string; role: string }>(
      '/api/v1/auth/me',
      tokenJson.access_token,
    )

    const session: AuthSession = {
      accessToken: tokenJson.access_token,
      refreshToken: tokenJson.refresh_token,
      role: tokenJson.role,
      userId: me.user_id,
      username: me.username,
    }
    this.saveSession(session)
    return session
  }

  async restoreSession(): Promise<AuthSession | null> {
    const stored = this.loadSession()
    if (!stored) return null

    try {
      const me = await this.client.get<{ user_id: string; username: string; role: string }>(
        '/api/v1/auth/me',
        stored.accessToken,
      )
      if (me.role !== 'RECYCLER') {
        this.clearSession()
        return null
      }
      const refreshed = { ...stored, userId: me.user_id, username: me.username }
      this.saveSession(refreshed)
      return refreshed
    } catch (err) {
      if (!(err instanceof ApiError) || !err.isInvalidToken) {
        this.clearSession()
        return null
      }
    }

    try {
      const refreshJson = await this.client.post<{ access_token: string }>('/api/v1/auth/refresh', {
        refresh_token: stored.refreshToken,
      })
      const me = await this.client.get<{ user_id: string; username: string; role: string }>(
        '/api/v1/auth/me',
        refreshJson.access_token,
      )
      if (me.role !== 'RECYCLER') {
        this.clearSession()
        return null
      }
      const refreshed = {
        ...stored,
        accessToken: refreshJson.access_token,
        userId: me.user_id,
        username: me.username,
      }
      this.saveSession(refreshed)
      return refreshed
    } catch {
      this.clearSession()
      return null
    }
  }

  async logout(session: AuthSession): Promise<void> {
    try {
      await this.client.post('/api/v1/auth/logout', undefined, session.accessToken)
    } catch {
      // Best-effort server-side invalidation; local session clears regardless.
    }
    this.clearSession()
  }

  private saveSession(session: AuthSession): void {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session))
  }

  private loadSession(): AuthSession | null {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    if (!raw) return null
    try {
      return JSON.parse(raw) as AuthSession
    } catch {
      this.clearSession()
      return null
    }
  }

  private clearSession(): void {
    localStorage.removeItem(SESSION_STORAGE_KEY)
  }
}

export const authRepository = new AuthRepository()
