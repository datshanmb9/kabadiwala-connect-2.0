import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../api/apiClient'
import { AuthProvider } from '../features/auth/AuthContext'
import { AuthRepository } from '../features/auth/authRepository'
import { Layout } from './Layout'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(
    'kc_admin_auth_session',
    JSON.stringify({ accessToken: 'acc-1', refreshToken: 'ref-1', role: 'GOVERNMENT_ADMIN', userId: 'admin-1', username: 'admin' }),
  )
})

function renderLayout(path = '/') {
  const fetchImpl = vi
    .fn()
    .mockResolvedValue(jsonResponse({ user_id: 'admin-1', username: 'admin', role: 'GOVERNMENT_ADMIN' }))
  const repository = new AuthRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl }))
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider repository={repository}>
        <Layout>
          <p>page content</p>
        </Layout>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('Admin navigation', () => {
  it('lists every remaining admin section with working links', async () => {
    renderLayout()
    const nav = await screen.findByRole('navigation', { name: 'Admin navigation' })
    const expected: Array<[string, string]> = [
      ['Dashboard', '/'],
      ['Recyclers', '/recyclers'],
      ['Collectors', '/collectors'],
      ['Wards', '/wards'],
      ['Operations', '/operations'],
      ['Rewards', '/rewards'],
      ['Complaints', '/complaints'],
      ['Audit Logs', '/audit-logs'],
    ]
    for (const [label, href] of expected) {
      expect(within(nav).getByRole('link', { name: label })).toHaveAttribute('href', href)
    }
    expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument()
    expect(screen.getByText('page content')).toBeInTheDocument()
  })

  it('no longer shows RRR Centres or Lots & Bids', async () => {
    renderLayout()
    await screen.findByRole('navigation', { name: 'Admin navigation' })
    expect(screen.queryByRole('link', { name: /RRR Centres/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Lots & Bids/i })).not.toBeInTheDocument()
    expect(document.querySelector('a[href="/rrr-centres"]')).toBeNull()
    expect(document.querySelector('a[href="/lots-bids"]')).toBeNull()
  })

  it('highlights the current section', async () => {
    renderLayout('/wards')
    const nav = await screen.findByRole('navigation', { name: 'Admin navigation' })
    expect(within(nav).getByRole('link', { name: 'Wards' })).toHaveClass('active')
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).not.toHaveClass('active')
  })
})
