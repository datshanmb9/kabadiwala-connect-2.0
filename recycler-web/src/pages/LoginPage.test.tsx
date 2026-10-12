import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../api/apiClient'
import { AuthProvider } from '../features/auth/AuthContext'
import { AuthRepository } from '../features/auth/authRepository'
import { LoginPage } from './LoginPage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

beforeEach(() => {
  localStorage.clear()
})

function renderLoginPage(fetchImpl: typeof fetch) {
  const repository = new AuthRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider repository={repository}>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  it('shows an inline error banner when login fails', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ success: false, error_code: 'INVALID_CREDENTIALS', message: 'Invalid username or password.' }, 401),
      )
    renderLoginPage(fetchImpl)

    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/username/i), 'demo-recycler-1')
    await user.type(screen.getByLabelText(/password/i), 'wrongpassword')
    await user.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => {
      expect(screen.getByText('Invalid username or password.')).toBeInTheDocument()
    })
  })

  it('rejects a non-RECYCLER role with a portal-specific message', async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(jsonResponse({ access_token: 'acc-1', refresh_token: 'ref-1', role: 'RRR_CENTER' }))
    renderLoginPage(fetchImpl)

    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/username/i), 'rrr-1')
    await user.type(screen.getByLabelText(/password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => {
      expect(screen.getByText(/for Recyclers only/i)).toBeInTheDocument()
    })
  })

  it('links to the registration page', () => {
    renderLoginPage(vi.fn())
    expect(screen.getByRole('link', { name: /register as a recycler/i })).toHaveAttribute('href', '/register')
  })
})
