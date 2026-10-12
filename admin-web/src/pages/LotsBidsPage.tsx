import { useEffect, useState } from 'react'
import { ApiError } from '../api/apiClient'
import { Layout, PageHeader } from '../components/Layout'
import { EmptyView, ErrorView, LoadingView, StatusBadge } from '../components/StateViews'
import { Table } from '../components/Table'
import { adminRepository } from '../features/admin/adminRepository'
import { useAuth } from '../features/auth/AuthContext'
import type { Bid, Lot } from '../types/domain'

export function LotsBidsPage() {
  const { session } = useAuth()
  const [lots, setLots] = useState<Lot[]>([])
  const [bids, setBids] = useState<Bid[]>([])
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
      const [l, b] = await Promise.all([
        adminRepository.listLots(session.accessToken),
        adminRepository.listBids(session.accessToken),
      ])
      setLots(l)
      setBids(b)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load lots/bids.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <PageHeader title="Lots & Bids" />
      {loading && <LoadingView />}
      {error && <ErrorView message={error} onRetry={load} />}
      {!loading && !error && (
        <>
          <h2>Lots</h2>
          {lots.length === 0 ? (
            <EmptyView message="No lots exist yet." />
          ) : (
            <Table
              rows={lots}
              rowKey={(l) => l.lot_id}
              columns={[
                { header: 'Lot ID', render: (l) => l.lot_id.slice(0, 8) + '…' },
                { header: 'RRR', render: (l) => l.rrr_id },
                { header: 'Ward', render: (l) => l.ward_id },
                { header: 'Category', render: (l) => l.category },
                { header: 'Items', render: (l) => l.item_ids.length },
                { header: 'Status', render: (l) => <StatusBadge status={l.status} /> },
                {
                  header: 'Bid Deadline',
                  render: (l) => (l.bid_deadline ? new Date(l.bid_deadline).toLocaleString() : '—'),
                },
              ]}
            />
          )}

          <h2>Bids</h2>
          {bids.length === 0 ? (
            <EmptyView message="No bids exist yet." />
          ) : (
            <Table
              rows={bids}
              rowKey={(b) => b.bid_id}
              columns={[
                { header: 'Bid ID', render: (b) => b.bid_id.slice(0, 8) + '…' },
                { header: 'Lot', render: (b) => b.lot_id.slice(0, 8) + '…' },
                { header: 'Recycler', render: (b) => b.recycler_id },
                { header: 'Amount (₹)', render: (b) => b.amount },
                { header: 'Status', render: (b) => <StatusBadge status={b.status} /> },
              ]}
            />
          )}
        </>
      )}
    </Layout>
  )
}
