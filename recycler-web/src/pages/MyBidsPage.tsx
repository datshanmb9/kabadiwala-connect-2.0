import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/apiClient'
import { generateIdempotencyKey } from '../api/idempotencyKey'
import { EmptyView, ErrorView, LoadingView, StatusBadge } from '../components/StateViews'
import { Layout, PageHeader } from '../components/Layout'
import { bidsRepository } from '../features/bids/bidsRepository'
import { useAuth } from '../features/auth/AuthContext'
import type { Bid } from '../types/domain'

export function MyBidsPage() {
  const { session } = useAuth()
  const [bids, setBids] = useState<Bid[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actioningId, setActioningId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const pendingKeys = useRef<Record<string, string>>({})

  useEffect(() => {
    void load()
  }, [])

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      setBids(await bidsRepository.listMyBids(session.accessToken))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load your bids.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCancel(bidId: string) {
    if (!session) return
    setActioningId(bidId)
    setActionError(null)
    const key = pendingKeys.current[bidId] ?? generateIdempotencyKey()
    pendingKeys.current[bidId] = key
    try {
      await bidsRepository.cancelBid(bidId, session.accessToken, key)
      delete pendingKeys.current[bidId]
      await load()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not cancel this bid.')
    } finally {
      setActioningId(null)
    }
  }

  return (
    <Layout approved>
      <PageHeader
        title="My Bids"
        description="Every bid you have placed and its outcome. Approved bids continue to logistics and payment from the lot page."
      />
      {actionError && <p className="inline-error-banner">{actionError}</p>}
      {loading && <LoadingView />}
      {error && <ErrorView message={error} onRetry={load} />}
      {!loading && !error && bids.length === 0 && (
        <EmptyView message="You haven't placed any bids yet." />
      )}
      <div className="bid-list">
        {bids.map((bid) => (
          <div key={bid.bid_id} className="card bid-row">
            <div>
              <dl className="facts">
                <div>
                  <dt>Lot</dt>
                  <dd>{bid.lot_id.slice(0, 8)}…</dd>
                </div>
                <div>
                  <dt>Amount</dt>
                  <dd className="bid-amount">₹{bid.amount}</dd>
                </div>
                <div>
                  <dt>Placed</dt>
                  <dd>{new Date(bid.placed_at).toLocaleString()}</dd>
                </div>
              </dl>
              {bid.status === 'ACCEPTED' && (
                <p className="callout callout-success">Your bid was approved. You have been selected for this lot.</p>
              )}
              {bid.status === 'REJECTED' && (
                <p className="callout callout-danger">Your bid was not approved for this lot.</p>
              )}
            </div>
            <div className="bid-actions">
              <StatusBadge status={bid.status} />
              {bid.status === 'PLACED' && (
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={actioningId === bid.bid_id}
                  onClick={() => void handleCancel(bid.bid_id)}
                >
                  {actioningId === bid.bid_id ? 'Cancelling…' : 'Cancel Bid'}
                </button>
              )}
              {bid.status === 'ACCEPTED' && (
                <Link to={`/lots/${bid.lot_id}`}>
                  <button type="button">View Lot — Book Logistics / Pay</button>
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </Layout>
  )
}
