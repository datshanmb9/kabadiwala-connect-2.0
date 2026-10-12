import { type FormEvent, useEffect, useState } from 'react'
import { ApiError } from '../api/apiClient'
import { Layout, PageHeader } from '../components/Layout'
import { ErrorView, InlineErrorBanner, LoadingView, StatusBadge } from '../components/StateViews'
import { Table } from '../components/Table'
import { adminRepository } from '../features/admin/adminRepository'
import { useAuth } from '../features/auth/AuthContext'
import type { Collector } from '../types/domain'

export function CollectorsPage() {
  const { session } = useAuth()
  const [rows, setRows] = useState<Collector[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actioningId, setActioningId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [reassignDrafts, setReassignDrafts] = useState<Record<string, string>>({})

  const [employeeId, setEmployeeId] = useState('')
  const [password, setPassword] = useState('')
  const [wardId, setWardId] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  useEffect(() => {
    void load()
  }, [])

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      setRows(await adminRepository.listCollectors(session.accessToken))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load collectors.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    if (!session) return
    setCreating(true)
    setCreateError(null)
    try {
      await adminRepository.createCollector({ employeeId, password, wardId }, session.accessToken)
      setEmployeeId('')
      setPassword('')
      setWardId('')
      await load()
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : 'Could not create this collector.')
    } finally {
      setCreating(false)
    }
  }

  async function handleReassign(userId: string) {
    if (!session) return
    const newWard = reassignDrafts[userId]?.trim()
    if (!newWard) return
    setActioningId(userId)
    setActionError(null)
    try {
      await adminRepository.updateCollectorAssignment(userId, { wardId: newWard }, session.accessToken)
      setReassignDrafts((prev) => ({ ...prev, [userId]: '' }))
      await load()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not reassign this collector.')
    } finally {
      setActioningId(null)
    }
  }

  async function toggleStatus(userId: string, currentStatus: string) {
    if (!session) return
    setActioningId(userId)
    setActionError(null)
    const newStatus = currentStatus === 'ACTIVE' ? 'DISABLED' : 'ACTIVE'
    try {
      await adminRepository.setCollectorStatus(userId, newStatus, session.accessToken)
      await load()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not change this collector\'s status.')
    } finally {
      setActioningId(null)
    }
  }

  return (
    <Layout>
      <PageHeader
        title="Collector Management"
        description="Create collector accounts, assign them to wards and control their access."
      />

      <div className="card">
        <h2>Create Collector</h2>
        <form onSubmit={handleCreate} className="inline-form">
          {createError && <InlineErrorBanner message={createError} />}
          <label>
            Employee ID
            <input value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} required minLength={3} />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </label>
          <label>
            Ward ID
            <input value={wardId} onChange={(e) => setWardId(e.target.value)} required />
          </label>
          <button type="submit" disabled={creating}>
            {creating ? 'Creating…' : 'Create'}
          </button>
        </form>
        <p className="hint">
          Employee ID becomes the login username. There is no collector self-registration — this is the only
          account-creation path, matching the architecture.
        </p>
      </div>

      {actionError && <p className="inline-error-banner">{actionError}</p>}
      {loading && <LoadingView />}
      {error && <ErrorView message={error} onRetry={load} />}
      {!loading && !error && (
        <Table
          rows={rows}
          rowKey={(r) => r.user_id}
          columns={[
            { header: 'Employee ID', render: (r) => r.employee_id },
            { header: 'Ward', render: (r) => r.ward_id },
            { header: 'RRR ID', render: (r) => r.rrr_id ?? '—' },
            { header: 'Status', render: (r) => <StatusBadge status={r.status} /> },
            {
              header: 'Reassign Ward',
              render: (r) => (
                <div className="row-actions">
                  <input
                    style={{ width: 100 }}
                    placeholder="New ward ID"
                    value={reassignDrafts[r.user_id] ?? ''}
                    onChange={(e) => setReassignDrafts((prev) => ({ ...prev, [r.user_id]: e.target.value }))}
                  />
                  <button type="button" disabled={actioningId === r.user_id} onClick={() => void handleReassign(r.user_id)}>
                    Save
                  </button>
                </div>
              ),
            },
            {
              header: 'Actions',
              render: (r) => (
                <button
                  type="button"
                  className={r.status === 'ACTIVE' ? 'btn-danger' : 'btn-secondary'}
                  disabled={actioningId === r.user_id}
                  onClick={() => void toggleStatus(r.user_id, r.status)}
                >
                  {r.status === 'ACTIVE' ? 'Disable' : 'Enable'}
                </button>
              ),
            },
          ]}
        />
      )}
    </Layout>
  )
}
