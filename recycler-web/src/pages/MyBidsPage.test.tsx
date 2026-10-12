import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../api/apiClient'
import { LoadingView } from '../components/StateViews'
import { AuthProvider, useAuth } from '../features/auth/AuthContext'
import { AuthRepository } from '../features/auth/authRepository'

// bidsRepository is a module-level singleton built on the real default
// ApiClient — mocked here for the same reason established in
// rrr-centre-web's ClassifyItemsPage.test.tsx (Phase 8): without this,
// the test would silently hit the real backend via Node's global fetch
// in the jsdom environment.
vi.mock('../features/bids/bidsRepository', () => ({
  bidsRepository: { listMyBids: vi.fn(), cancelBid: vi.fn() },
}))

const { bidsRepository } = await import('../features/bids/bidsRepository')
const { MyBidsPage } = await import('./MyBidsPage')

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

const STORED_SESSION = {
  accessToken: 'acc-1',
  refreshToken: 'ref-1',
  role: 'RECYCLER',
  userId: 'recycler-1',
  username: 'demo-recycler-1',
}

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('kc_recycler_auth_session', JSON.stringify(STORED_SESSION))
  vi.mocked(bidsRepository.listMyBids).mockReset()
})

function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status !== 'authenticated') return <LoadingView />
  return <>{children}</>
}

function renderPage() {
  const authFetch = vi
    .fn()
    .mockResolvedValue(jsonResponse({ user_id: 'recycler-1', username: 'demo-recycler-1', role: 'RECYCLER' }))
  const repository = new AuthRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl: authFetch }))
  return render(
    <MemoryRouter>
      <AuthProvider repository={repository}>
        <RequireAuth>
          <MyBidsPage />
        </RequireAuth>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('MyBidsPage — Phase 10 navigation fix', () => {
  it('shows a link to the lot detail page for an ACCEPTED bid (previously missing entirely)', async () => {
    vi.mocked(bidsRepository.listMyBids).mockResolvedValue([
      {
        bid_id: 'bid-1', lot_id: 'lot-12345678', recycler_id: 'demo-recycler-1', amount: '500.00',
        status: 'ACCEPTED', placed_at: '2026-10-01T00:00:00', accepted_at: '2026-10-01T01:00:00',
      },
    ])
    renderPage()

    await waitFor(() => {
      const link = screen.getByRole('link', { name: /view lot/i })
      expect(link).toHaveAttribute('href', '/lots/lot-12345678')
    })
  })

  it('does not show the lot link or cancel button for a REJECTED bid', async () => {
    vi.mocked(bidsRepository.listMyBids).mockResolvedValue([
      {
        bid_id: 'bid-2', lot_id: 'lot-1', recycler_id: 'demo-recycler-1', amount: '400.00',
        status: 'REJECTED', placed_at: '2026-10-01T00:00:00', accepted_at: null,
      },
    ])
    renderPage()

    await waitFor(() => expect(screen.getByText(/REJECTED/)).toBeInTheDocument())
    expect(screen.queryByRole('link', { name: /view lot/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /cancel bid/i })).not.toBeInTheDocument()
  })

  it('still shows the Cancel Bid button (not the lot link) for a PLACED bid', async () => {
    vi.mocked(bidsRepository.listMyBids).mockResolvedValue([
      {
        bid_id: 'bid-3', lot_id: 'lot-1', recycler_id: 'demo-recycler-1', amount: '300.00',
        status: 'PLACED', placed_at: '2026-10-01T00:00:00', accepted_at: null,
      },
    ])
    renderPage()

    await waitFor(() => expect(screen.getByRole('button', { name: /cancel bid/i })).toBeInTheDocument())
    expect(screen.queryByRole('link', { name: /view lot/i })).not.toBeInTheDocument()
  })
})
