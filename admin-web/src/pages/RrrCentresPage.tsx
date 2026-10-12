import { useEffect, useState } from 'react'
import { ApiError } from '../api/apiClient'
import { Layout, PageHeader } from '../components/Layout'
import { ErrorView, LoadingView, StatusBadge } from '../components/StateViews'
import { Table } from '../components/Table'
import { adminRepository } from '../features/admin/adminRepository'
import { useAuth } from '../features/auth/AuthContext'
import type { RrrCentre } from '../types/domain'

export function RrrCentresPage() {
  const { session } = useAuth()
  const [rows, setRows] = useState<RrrCentre[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actioningId, setActioningId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    void load()
  }, [])

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      setRows(await adminRepository.listRrrCentres(session.accessToken))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load RRR centres.')
    } finally {
      setLoading(false)
    }
  }

  async function act(userId: string, action: 'approve' | 'reject') {
    if (!session) return
    setActioningId(userId)
    setActionError(null)
    try {
      if (action === 'approve') await adminRepository.approveRrrCentre(userId, session.accessToken)
      else await adminRepository.rejectRrrCentre(userId, session.accessToken)
      await load()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Action failed.')
    } finally {
      setActioningId(null)
    }
  }

  return (
    <Layout>
      <PageHeader title="RRR Centres" />
      {actionError && <p className="inline-error-banner">{actionError}</p>}
      {loading && <LoadingView />}
      {error && <ErrorView message={error} onRetry={load} />}
      {!loading && !error && (
        <Table
          rows={rows}
          rowKey={(r) => r.user_id}
          columns={[
            { header: 'RRR ID', render: (r) => r.rrr_id },
            { header: 'Username', render: (r) => r.username },
            { header: 'Tender ID', render: (r) => r.tender_id },
            { header: 'Ward', render: (r) => r.ward_id },
            { header: 'Status', render: (r) => <StatusBadge status={r.status} /> },
            {
              header: 'Actions',
              render: (r) =>
                r.status === 'PENDING' ? (
                  <div className="row-actions">
                    <button type="button" disabled={actioningId === r.user_id} onClick={() => void act(r.user_id, 'approve')}>
                      Approve
                    </button>
                    <button
                      type="button"
                      className="btn-danger"
                      disabled={actioningId === r.user_id}
                      onClick={() => void act(r.user_id, 'reject')}
                    >
                      Reject
                    </button>
                  </div>
                ) : (
                  <span className="hint">—</span>
                ),
            },
          ]}
        />
      )}
    </Layout>
  )
}
