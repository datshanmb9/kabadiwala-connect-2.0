import { type FormEvent, useEffect, useState } from 'react'
import { ApiError } from '../api/apiClient'
import { Layout, PageHeader } from '../components/Layout'
import { EmptyView, ErrorView, InlineErrorBanner, LoadingView, StatusBadge } from '../components/StateViews'
import { Table } from '../components/Table'
import { adminRepository } from '../features/admin/adminRepository'
import { useAuth } from '../features/auth/AuthContext'
import type { Payment, Reward } from '../types/domain'

export function RewardsPage() {
  const { session } = useAuth()
  const [rewards, setRewards] = useState<Reward[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [period, setPeriod] = useState('')
  const [computing, setComputing] = useState(false)
  const [computeError, setComputeError] = useState<string | null>(null)
  const [computeResult, setComputeResult] = useState<string | null>(null)

  useEffect(() => {
    void load()
  }, [])

  async function load() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const [r, p] = await Promise.all([
        adminRepository.listRewards(session.accessToken),
        adminRepository.listPayments(session.accessToken),
      ])
      setRewards(r)
      setPayments(p)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load reward/payment data.')
    } finally {
      setLoading(false)
    }
  }

  async function handleCompute(e: FormEvent) {
    e.preventDefault()
    if (!session) return
    setComputing(true)
    setComputeError(null)
    setComputeResult(null)
    try {
      const created = await adminRepository.computeRewards(period, session.accessToken)
      setComputeResult(`${created.length} new reward(s) credited for ${period}.`)
      await load()
    } catch (err) {
      setComputeError(err instanceof ApiError ? err.message : 'Could not compute rewards for this period.')
    } finally {
      setComputing(false)
    }
  }

  return (
    <Layout>
      <PageHeader title="Rewards" description="Compute monthly home-user rewards and review reward and payment records." />

      <div className="card">
        <h2>Compute Monthly Rewards</h2>
        <p className="hint">
          Eligibility is keyed entirely on each item's immutable reward_eligible_at timestamp (stamped once, at
          COLLECTED) — never on its current status. Re-running a period is safe: an already-credited home user is
          skipped, never double-credited. There is no clawback action anywhere in this system.
        </p>
        <form onSubmit={handleCompute} className="inline-form">
          {computeError && <InlineErrorBanner message={computeError} />}
          <label>
            Period (YYYY-MM)
            <input
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              placeholder="2026-09"
              pattern="\d{4}-\d{2}"
              required
            />
          </label>
          <button type="submit" disabled={computing}>
            {computing ? 'Computing…' : 'Compute'}
          </button>
        </form>
        {computeResult && <p className="hint">{computeResult}</p>}
      </div>

      {loading && <LoadingView />}
      {error && <ErrorView message={error} onRetry={load} />}
      {!loading && !error && (
        <>
          <h2>Rewards</h2>
          {rewards.length === 0 ? (
            <EmptyView message="No rewards have been computed yet." />
          ) : (
            <Table
              rows={rewards}
              rowKey={(r) => r.reward_id}
              columns={[
                { header: 'Home User', render: (r) => r.home_user_id.slice(0, 8) + '…' },
                { header: 'Period', render: (r) => r.period },
                { header: 'Points', render: (r) => r.points },
                { header: 'Amount (₹)', render: (r) => r.amount },
                { header: 'Status', render: (r) => <StatusBadge status={r.status} /> },
              ]}
            />
          )}

          <h2>Payments</h2>
          {payments.length === 0 ? (
            <EmptyView message="No payments have been attempted yet." />
          ) : (
            <Table
              rows={payments}
              rowKey={(p) => p.payment_id}
              columns={[
                { header: 'Lot', render: (p) => p.lot_id.slice(0, 8) + '…' },
                { header: 'Recycler', render: (p) => p.recycler_id },
                { header: 'Amount (₹)', render: (p) => p.amount },
                { header: 'Status', render: (p) => <StatusBadge status={p.status} /> },
                { header: 'Gateway', render: (p) => p.gateway },
                { header: 'Reference', render: (p) => p.gateway_reference ?? '—' },
              ]}
            />
          )}
        </>
      )}
    </Layout>
  )
}
