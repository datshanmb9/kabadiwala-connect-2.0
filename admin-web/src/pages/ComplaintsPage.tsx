import { useEffect, useState } from 'react'
import { ApiError } from '../api/apiClient'
import { Layout, PageHeader } from '../components/Layout'
import { EmptyView, ErrorView, LoadingView, StatusBadge } from '../components/StateViews'
import { Table } from '../components/Table'
import { adminRepository } from '../features/admin/adminRepository'
import { useAuth } from '../features/auth/AuthContext'
import type { Complaint } from '../types/domain'

const NEXT_STATUS: Record<string, string[]> = {
  OPEN: ['IN_PROGRESS'],
  IN_PROGRESS: ['RESOLVED', 'REJECTED', 'ESCALATED'],
  RESOLVED: [],
  REJECTED: [],
  ESCALATED: [],
}

export function ComplaintsPage() {
  const { session } = useAuth()
  const [rows, setRows] = useState<Complaint[]>([])
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
      setRows(await adminRepository.listComplaints(session.accessToken))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load complaints.')
    } finally {
      setLoading(false)
    }
  }

  async function review(complaintId: string, newStatus: string) {
    if (!session) return
    setActioningId(complaintId)
    setActionError(null)
    try {
      await adminRepository.reviewComplaint(complaintId, newStatus, session.accessToken)
      await load()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not update this complaint.')
    } finally {
      setActioningId(null)
    }
  }

  return (
    <Layout>
      <PageHeader title="Complaints" description="Review and resolve complaints filed across the platform." />
      {actionError && <p className="inline-error-banner">{actionError}</p>}
      {loading && <LoadingView />}
      {error && <ErrorView message={error} onRetry={load} />}
      {!loading && !error && rows.length === 0 && <EmptyView message="No complaints have been filed yet." />}
      {!loading && !error && rows.length > 0 && (
        <Table
          rows={rows}
          rowKey={(c) => c.complaint_id}
          columns={[
            { header: 'Category', render: (c) => c.category },
            { header: 'Target', render: (c) => `${c.target_type}: ${c.target_id}` },
            { header: 'Reporter', render: (c) => c.reporter_role },
            { header: 'Description', render: (c) => c.description },
            { header: 'Status', render: (c) => <StatusBadge status={c.status} /> },
            {
              header: 'Actions',
              render: (c) => {
                const options = NEXT_STATUS[c.status] ?? []
                if (options.length === 0) return <span className="hint">—</span>
                return (
                  <div className="row-actions">
                    {options.map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        disabled={actioningId === c.complaint_id}
                        onClick={() => void review(c.complaint_id, opt)}
                      >
                        {opt.replaceAll('_', ' ')}
                      </button>
                    ))}
                  </div>
                )
              },
            },
          ]}
        />
      )}
    </Layout>
  )
}
