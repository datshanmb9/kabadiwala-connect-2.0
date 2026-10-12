import { type FormEvent, useEffect, useState } from 'react'
import { ApiError } from '../api/apiClient'
import { Layout, PageHeader } from '../components/Layout'
import { ErrorView, InlineErrorBanner, LoadingView } from '../components/StateViews'
import { Table } from '../components/Table'
import { adminRepository } from '../features/admin/adminRepository'
import { useAuth } from '../features/auth/AuthContext'
import type { Collector, RrrCentre, Ward } from '../types/domain'

export function WardsPage() {
  const { session } = useAuth()
  const [wards, setWards] = useState<Ward[]>([])
  const [rrrCentres, setRrrCentres] = useState<RrrCentre[]>([])
  const [collectors, setCollectors] = useState<Collector[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [wardId, setWardId] = useState('')
  const [name, setName] = useState('')
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
      const [w, r, c] = await Promise.all([
        adminRepository.listWards(session.accessToken),
        adminRepository.listRrrCentres(session.accessToken),
        adminRepository.listCollectors(session.accessToken),
      ])
      setWards(w)
      setRrrCentres(r)
      setCollectors(c)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load ward data.')
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
      await adminRepository.createWard(wardId, name, session.accessToken)
      setWardId('')
      setName('')
      await load()
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : 'Could not create this ward.')
    } finally {
      setCreating(false)
    }
  }

  return (
    <Layout>
      <PageHeader title="Ward Management" description="Wards, their linked RRR centre and assigned collectors." />

      <div className="card">
        <h2>Create Ward</h2>
        <form onSubmit={handleCreate} className="inline-form">
          {createError && <InlineErrorBanner message={createError} />}
          <label>
            Ward ID
            <input value={wardId} onChange={(e) => setWardId(e.target.value)} required />
          </label>
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <button type="submit" disabled={creating}>
            {creating ? 'Creating…' : 'Create'}
          </button>
        </form>
      </div>

      {loading && <LoadingView />}
      {error && <ErrorView message={error} onRetry={load} />}
      {!loading && !error && (
        <>
          <p className="hint">
            Ward↔RRR linkage is one-time, set only when an RRR centre is approved — there is no reassignment
            endpoint by design, protected by a database-level partial unique index.
          </p>
          <Table
            rows={wards}
            rowKey={(w) => w.ward_id}
            columns={[
              { header: 'Ward ID', render: (w) => w.ward_id },
              { header: 'Name', render: (w) => w.name },
              {
                header: 'RRR Centre',
                render: (w) => {
                  const linkedRrr = rrrCentres.find((r) => r.ward_id === w.ward_id && r.status === 'APPROVED')
                  return linkedRrr ? `${linkedRrr.rrr_id} (${linkedRrr.username})` : '—'
                },
              },
              {
                header: 'Collectors',
                render: (w) => {
                  const assigned = collectors.filter((c) => c.ward_id === w.ward_id)
                  return assigned.length > 0 ? assigned.map((c) => c.employee_id).join(', ') : '—'
                },
              },
            ]}
          />
        </>
      )}
    </Layout>
  )
}
