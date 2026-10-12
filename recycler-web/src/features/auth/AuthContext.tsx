import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { ApiError } from '../../api/apiClient'
import type { AuthSession } from '../../types/domain'
import { AuthRepository, WrongRoleError, authRepository as defaultAuthRepository } from './authRepository'

export type AuthStatus = 'unknown' | 'working' | 'authenticated' | 'unauthenticated'

interface AuthContextValue {
  status: AuthStatus
  session: AuthSession | null
  errorMessage: string | null
  login: (username: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({
  children,
  repository = defaultAuthRepository,
}: {
  children: ReactNode
  repository?: AuthRepository
}) {
  const [status, setStatus] = useState<AuthStatus>('unknown')
  const [session, setSession] = useState<AuthSession | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setStatus('working')
    repository
      .restoreSession()
      .then((restored) => {
        if (cancelled) return
        setSession(restored)
        setStatus(restored ? 'authenticated' : 'unauthenticated')
      })
      .catch(() => {
        if (cancelled) return
        setSession(null)
        setStatus('unauthenticated')
      })
    return () => {
      cancelled = true
    }
  }, [repository])

  const login = useCallback(
    async (username: string, password: string) => {
      setStatus('working')
      setErrorMessage(null)
      try {
        const newSession = await repository.login(username, password)
        setSession(newSession)
        setStatus('authenticated')
        return true
      } catch (err) {
        if (err instanceof WrongRoleError) {
          setErrorMessage('This portal is for Recyclers only.')
        } else if (err instanceof ApiError) {
          setErrorMessage(err.message)
        } else {
          setErrorMessage('Something went wrong. Please try again.')
        }
        setStatus('unauthenticated')
        return false
      }
    },
    [repository],
  )

  const logout = useCallback(async () => {
    const current = session
    setSession(null)
    setStatus('unauthenticated')
    if (current) await repository.logout(current)
  }, [repository, session])

  return (
    <AuthContext.Provider value={{ status, session, errorMessage, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
