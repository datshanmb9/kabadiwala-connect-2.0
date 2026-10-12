import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/apiClient'
import { Icon } from '../components/Icon'
import { Layout, PageHeader } from '../components/Layout'
import { ErrorView, LoadingView, StatusBadge } from '../components/StateViews'
import { adminRepository } from '../features/admin/adminRepository'
import { useAuth } from '../features/auth/AuthContext'
import type { DashboardSummary } from '../types/domain'

function Tile({ label, value, tone }: { label: string; value: number; tone?: 'accent' | 'danger' }) {
  return (
    <div className={`summary-tile${tone ? ` tone-${tone}` : ''}`}>
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  )
}

function StatusBreakdown({ title, byStatus }: { title: string; byStatus: Record<string, number> }) {
  const entries = Object.entries(byStatus)
  return (
    <div className="card">
      <h2>{title}</h2>
      {entries.length === 0 ? (
        <p className="hint">None yet</p>
      ) : (
        <div className="breakdown">
          {entries.map(([status, count]) => (
            <span key={status} className="breakdown-item">
              <StatusBadge status={status} />
              <span className="breakdown-count">{count}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

const QUICK_LINKS = [
  { to: '/recyclers', label: 'Review recyclers', icon: 'recycler' },
  { to: '/collectors', label: 'Manage collectors', icon: 'collectors' },
  { to: '/wards', label: 'Wards', icon: 'wards' },
  { to: '/operations', label: 'Operations', icon: 'operations' },
  { to: '/complaints', label: 'Complaints', icon: 'complaints' },
]

export function DashboardPage() {
  const { session } = useAuth()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
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
      setSummary(await adminRepository.getDashboardSummary(session.accessToken))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load the dashboard summary.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <PageHeader
        title="Dashboard"
        description="System-wide overview of users, collections and marketplace activity across all wards."
      />
      {loading && <LoadingView message="Loading summary…" />}
      {error && <ErrorView message={error} onRetry={load} />}
      {summary && (
        <>
          <div className="summary-grid">
            <Tile label="Home Users" value={summary.users_by_role.HOME_USER ?? 0} tone="accent" />
            <Tile label="Collectors" value={summary.users_by_role.COLLECTOR ?? 0} tone="accent" />
            <Tile label="RRR Centres" value={summary.users_by_role.RRR_CENTER ?? 0} />
            <Tile label="Recyclers" value={summary.users_by_role.RECYCLER ?? 0} />
            <Tile label="Wards" value={summary.wards_count} />
            <Tile label="Flagged Submissions" value={summary.flagged_submissions_count} tone="danger" />
          </div>

          <div className="quick-links">
            {QUICK_LINKS.map((link) => (
              <Link key={link.to} to={link.to}>
                <Icon name={link.icon} size={16} />
                {link.label}
              </Link>
            ))}
          </div>

          <div className="card-grid">
            <StatusBreakdown title="Submissions by status" byStatus={summary.submissions_by_status} />
            <StatusBreakdown title="Recyclers by status" byStatus={summary.recyclers_by_status} />
            <StatusBreakdown title="RRR Centres by status" byStatus={summary.rrr_centres_by_status} />
            <StatusBreakdown title="Lots by status" byStatus={summary.lots_by_status} />
            <StatusBreakdown title="Bids by status" byStatus={summary.bids_by_status} />
            <StatusBreakdown title="Complaints by status" byStatus={summary.complaints_by_status} />
          </div>
        </>
      )}
    </Layout>
  )
}
