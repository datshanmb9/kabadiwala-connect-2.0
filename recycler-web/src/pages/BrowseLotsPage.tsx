import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/apiClient'
import { EmptyView, ErrorView, LoadingView, StatusBadge } from '../components/StateViews'
import { Layout, PageHeader } from '../components/Layout'
import { useAuth } from '../features/auth/AuthContext'
import { lotsRepository } from '../features/lots/lotsRepository'
import type { Lot } from '../types/domain'

export function BrowseLotsPage() {
  const { session } = useAuth()
  const [lots, setLots] = useState<Lot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void load()
  }, [])

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      setLots(await lotsRepository.listListedForBidding(session.accessToken))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load available lots.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout approved>
      <PageHeader
        title="Available Lots"
        description="Every lot currently open for bidding, from any RRR Centre. Open a lot to see its estimated price and place a bid."
      />
      {loading && <LoadingView />}
      {error && <ErrorView message={error} onRetry={load} />}
      {!loading && !error && lots.length === 0 && (
        <EmptyView message="No lots are currently open for bidding." />
      )}
      <div className="lot-grid">
        {lots.map((lot) => (
          <Link key={lot.lot_id} to={`/lots/${lot.lot_id}`} className="lot-card-link">
            <div className="card lot-card">
              <div className="lot-card-head">
                <span className="lot-card-title">{lot.category}</span>
                <StatusBadge status={lot.status} />
              </div>
              <dl className="facts">
                <div>
                  <dt>Items</dt>
                  <dd>{lot.item_ids.length}</dd>
                </div>
                <div>
                  <dt>Ward</dt>
                  <dd>{lot.ward_id}</dd>
                </div>
                {lot.total_weight_kg != null && (
                  <div>
                    <dt>Weight</dt>
                    <dd>{lot.total_weight_kg.toFixed(2)} kg</dd>
                  </div>
                )}
                {lot.bid_deadline && (
                  <div>
                    <dt>Bid deadline</dt>
                    <dd>{new Date(lot.bid_deadline).toLocaleString()}</dd>
                  </div>
                )}
              </dl>
              <span className="lot-card-cta">View details &amp; bid →</span>
            </div>
          </Link>
        ))}
      </div>
    </Layout>
  )
}
