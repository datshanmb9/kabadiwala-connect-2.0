import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClient } from '../api/apiClient'
import { LoadingView } from '../components/StateViews'
import { AuthProvider, useAuth } from '../features/auth/AuthContext'
import { AuthRepository } from '../features/auth/authRepository'
import type { Lot } from '../types/domain'

// Module-level singletons mocked so the test never reaches a real backend
// (same reason as MyBidsPage.test.tsx).
vi.mock('../features/lots/lotsRepository', () => ({
  lotsRepository: { getLot: vi.fn(), listListedForBidding: vi.fn() },
}))

vi.mock('../features/bids/bidsRepository', () => ({
  bidsRepository: { placeBid: vi.fn(), listMyBids: vi.fn(), cancelBid: vi.fn() },
}))

const { lotsRepository } = await import('../features/lots/lotsRepository')
const { bidsRepository } = await import('../features/bids/bidsRepository')
const { LotDetailPage } = await import('./LotDetailPage')

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

const BASE_LOT: Lot = {
  lot_id: 'lot-12345678',
  rrr_id: '',
  ward_id: 'WARD-1',
  category: 'e-waste-small-appliances',
  item_ids: ['sub-1'],
  status: 'LISTED_FOR_BIDDING',
  bid_deadline: '2026-10-01T00:00:00',
  total_weight_kg: 0.4,
  item_details: [],
}

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(
    'kc_recycler_auth_session',
    JSON.stringify({ accessToken: 'acc-1', refreshToken: 'ref-1', role: 'RECYCLER', userId: 'r-1', username: 'r-1' }),
  )
  vi.mocked(lotsRepository.getLot).mockReset()
})

function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status !== 'authenticated') return <LoadingView />
  return <>{children}</>
}

function renderPage() {
  const authFetch = vi.fn().mockResolvedValue(jsonResponse({ user_id: 'r-1', username: 'r-1', role: 'RECYCLER' }))
  const repository = new AuthRepository(new ApiClient({ baseUrl: 'http://test', fetchImpl: authFetch }))
  return render(
    <MemoryRouter initialEntries={['/lots/lot-12345678']}>
      <AuthProvider repository={repository}>
        <RequireAuth>
          <Routes>
            <Route path="/lots/:lotId" element={<LotDetailPage />} />
          </Routes>
        </RequireAuth>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('LotDetailPage — price estimate', () => {
  it('shows the backend estimate per kg and total range before bidding', async () => {
    vi.mocked(lotsRepository.getLot).mockResolvedValue({
      ...BASE_LOT,
      price_estimate: {
        predicted_price_per_kg: 109.12,
        min_price: 98.21,
        max_price: 120.03,
        weight_kg: 0.4,
        estimated_total_min: 39.28,
        estimated_total_max: 48.01,
        is_estimate: true,
        model_version: 'collector_price_model.joblib',
        estimated_at: null,
      },
    })
    renderPage()

    await waitFor(() => expect(screen.getByText('Estimated Price')).toBeInTheDocument())
    const priceLine = screen.getByText('Estimated price:').closest('p')
    const totalLine = screen.getByText('Estimated total:').closest('p')
    expect(priceLine).toHaveTextContent('Estimated price: ₹98.21 – ₹120.03 / kg')
    expect(totalLine).toHaveTextContent('Estimated total: ₹39.28 – ₹48.01')
    expect(screen.getByRole('button', { name: 'Place Bid' })).toBeInTheDocument()
  })

  it('omits the section when the backend has no estimate for the lot', async () => {
    vi.mocked(lotsRepository.getLot).mockResolvedValue({ ...BASE_LOT, price_estimate: null })
    renderPage()

    await waitFor(() => expect(screen.getByText('Lot Detail')).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText(/Collected weight:/)).toBeInTheDocument())
    expect(screen.queryByText('Estimated Price')).not.toBeInTheDocument()
  })

  it('placing a bid still calls the bids API and shows the placed bid', async () => {
    vi.mocked(lotsRepository.getLot).mockResolvedValue({ ...BASE_LOT, price_estimate: null })
    vi.mocked(bidsRepository.placeBid).mockResolvedValue({
      bid_id: 'bid-1', lot_id: 'lot-12345678', recycler_id: 'r-1', amount: '45.00',
      status: 'PLACED', placed_at: '2026-10-01T00:00:00', accepted_at: null,
    })
    renderPage()

    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/Bid amount/), '45.00')
    await user.click(screen.getByRole('button', { name: 'Place Bid' }))

    await waitFor(() => expect(screen.getByText('Bid placed')).toBeInTheDocument())
    expect(vi.mocked(bidsRepository.placeBid).mock.calls[0].slice(0, 3)).toEqual(['lot-12345678', '45.00', 'acc-1'])
    expect(screen.getByText('PLACED')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Place Bid' })).not.toBeInTheDocument()
  })
})
