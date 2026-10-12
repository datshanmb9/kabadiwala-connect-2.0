import { useEffect, useState } from 'react'
import { ApiError } from '../api/apiClient'
import { Layout, PageHeader } from '../components/Layout'
import { EmptyView, ErrorView, LoadingView, StatusBadge } from '../components/StateViews'
import { Table } from '../components/Table'
import { adminRepository } from '../features/admin/adminRepository'
import { useAuth } from '../features/auth/AuthContext'
import type { Handover, Submission } from '../types/domain'

// Phase 10 fix: this list had not been updated since Phase 7 — every
// status an item can reach from Phase 8 (NEEDS_REVIEW) and Phase 9
// (LOGISTICS_BOOKED onward) was unreachable through this filter, even
// though the backend already returns/accepts them.
const SUBMISSION_STATUSES = [
  '',
  'WAITING_FOR_COLLECTION',
  'HANDOVER_PENDING',
  'COLLECTED',
  'FLAGGED_FOR_REVIEW',
  'AT_RRR',
  'CLASSIFIED',
  'NEEDS_REVIEW',
  'LOT_CREATED',
  'LISTED_FOR_BIDDING',
  'BID_SELECTED',
  'LOGISTICS_BOOKED',
  'READY_FOR_COLLECTION',
  'PAYMENT_PENDING',
  'PAID',
  'COMPLETED',
]

export function OperationsPage() {
  const { session } = useAuth()
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [handovers, setHandovers] = useState<Handover[]>([])
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void load()
  }, [statusFilter])

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const [s, h] = await Promise.all([
        adminRepository.listSubmissions(session.accessToken, statusFilter || undefined),
        adminRepository.listHandovers(session.accessToken, statusFilter === 'FLAGGED_FOR_REVIEW' ? 'FLAGGED' : undefined),
      ])
      setSubmissions(s)
      setHandovers(h)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load operational data.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <PageHeader
        title="E-waste Operations"
        description="Track submissions through their lifecycle and review handover geo-verification results."
      />
      <div className="filter-bar">
        <label>
          Filter by status
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            {SUBMISSION_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s || 'All'}
              </option>
            ))}
          </select>
        </label>
      </div>
      {loading && <LoadingView />}
      {error && <ErrorView message={error} onRetry={load} />}
      {!loading && !error && (
        <>
          <h2>Submissions</h2>
          {submissions.length === 0 ? (
            <EmptyView message="No submissions match this filter." />
          ) : (
            <Table
              rows={submissions}
              rowKey={(s) => s.submission_id}
              columns={[
                { header: 'Submission ID', render: (s) => s.submission_id.slice(0, 8) + '…' },
                { header: 'Ward', render: (s) => s.ward_id },
                { header: 'Category', render: (s) => s.category ?? '—' },
                { header: 'Status', render: (s) => <StatusBadge status={s.status} /> },
              ]}
            />
          )}

          <h2>Handovers (geo-verification detail)</h2>
          {handovers.length === 0 ? (
            <EmptyView message="No handovers match this filter." />
          ) : (
            <Table
              rows={handovers}
              rowKey={(h) => h.submission_id}
              columns={[
                { header: 'Submission ID', render: (h) => h.submission_id.slice(0, 8) + '…' },
                { header: 'Collector', render: (h) => h.collector_id.slice(0, 8) + '…' },
                { header: 'Distance (m)', render: (h) => (h.distance_m != null ? h.distance_m.toFixed(1) : '—') },
                { header: 'Result', render: (h) => <StatusBadge status={h.verification_result} /> },
                { header: 'Reasons', render: (h) => h.failure_reasons.join(', ') || '—' },
              ]}
            />
          )}
        </>
      )}
    </Layout>
  )
}
