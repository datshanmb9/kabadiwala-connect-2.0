import { useEffect, useState } from 'react'
import { ApiError } from '../api/apiClient'
import { Layout, PageHeader } from '../components/Layout'
import { EmptyView, ErrorView, LoadingView } from '../components/StateViews'
import { Table } from '../components/Table'
import { adminRepository } from '../features/admin/adminRepository'
import { useAuth } from '../features/auth/AuthContext'
import type { AuditLogEntry } from '../types/domain'

export function AuditLogsPage() {
  const { session } = useAuth()
  const [rows, setRows] = useState<AuditLogEntry[]>([])
  const [governmentActionsOnly, setGovernmentActionsOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void load()
  }, [governmentActionsOnly])

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      setRows(
        await adminRepository.listAuditLogs(
          session.accessToken,
          governmentActionsOnly ? { actorRole: 'GOVERNMENT_ADMIN' } : {},
        ),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load audit logs.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <PageHeader
        title="Audit Logs"
        description={
          <>
            Append-only — there is no edit/delete path for this collection, for any role. "Government Actions"
            filters to entries where the acting role was GOVERNMENT_ADMIN (approvals, collector management,
            complaint review).
          </>
        }
      />
      <div className="filter-bar">
        <label>
          <input
            type="checkbox"
            style={{ width: 'auto' }}
            checked={governmentActionsOnly}
            onChange={(e) => setGovernmentActionsOnly(e.target.checked)}
          />
          {' '}Government Actions only
        </label>
      </div>
      {loading && <LoadingView />}
      {error && <ErrorView message={error} onRetry={load} />}
      {!loading && !error && rows.length === 0 && <EmptyView message="No audit log entries match this filter." />}
      {!loading && !error && rows.length > 0 && (
        <Table
          rows={rows}
          rowKey={(l) => l.log_id}
          columns={[
            { header: 'Time', render: (l) => new Date(l.timestamp).toLocaleString() },
            { header: 'Actor Role', render: (l) => l.actor_role ?? '—' },
            { header: 'Action', render: (l) => l.action },
            { header: 'Entity', render: (l) => `${l.entity_type}: ${l.entity_id.slice(0, 8)}…` },
            { header: 'Details', render: (l) => JSON.stringify(l.details) },
          ]}
        />
      )}
    </Layout>
  )
}
