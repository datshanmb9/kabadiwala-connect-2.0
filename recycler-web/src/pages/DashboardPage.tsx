import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/apiClient'
import { Card, ErrorView, LoadingView, StatusBadge } from '../components/StateViews'
import { Layout, PageHeader } from '../components/Layout'
import { useAuth } from '../features/auth/AuthContext'
import { bidsRepository } from '../features/bids/bidsRepository'
import { lotsRepository } from '../features/lots/lotsRepository'
import { recyclerRepository } from '../features/recycler/recyclerRepository'
import type { Bid, RecyclerProfile } from '../types/domain'

interface Overview {
  openLots: number
  bids: Bid[]
}

export function DashboardPage() {
  const { session } = useAuth()
  const [profile, setProfile] = useState<RecyclerProfile | null>(null)
  const [overview, setOverview] = useState<Overview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void loadProfile()
  }, [])

  async function loadProfile() {
    if (!session) return
    setLoading(true)
    setError(null)
    try {
      const p = await recyclerRepository.getProfile(session.accessToken)
      setProfile(p)
      if (p.status === 'APPROVED') void loadOverview(session.accessToken)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load your profile.')
    } finally {
      setLoading(false)
    }
  }

  /** At-a-glance counts from the same list endpoints Browse Lots and My
   * Bids use; purely informational, so a failure just hides the tiles. */
  async function loadOverview(token: string) {
    try {
      const [lots, bids] = await Promise.all([
        lotsRepository.listListedForBidding(token),
        bidsRepository.listMyBids(token),
      ])
      setOverview({ openLots: lots.length, bids })
    } catch {
      setOverview(null)
    }
  }

  const approved = profile?.status === 'APPROVED'
  const countBids = (status: string) => overview?.bids.filter((b) => b.status === status).length ?? 0

  return (
    <Layout approved={approved}>
      <PageHeader title="Dashboard" description="Your recycler account and marketplace activity at a glance." />
      {loading && <LoadingView message="Loading your profile…" />}
      {error && <ErrorView message={error} onRetry={loadProfile} />}
      {profile && (
        <>
          <Card>
            <div className="profile-card">
              <div>
                <h2>{profile.company_name}</h2>
                <dl className="facts">
                  <div>
                    <dt>License ID</dt>
                    <dd>{profile.license_id}</dd>
                  </div>
                  <div>
                    <dt>Username</dt>
                    <dd>{profile.username}</dd>
                  </div>
                </dl>
              </div>
              <StatusBadge status={profile.status} />
            </div>

            {profile.status === 'PENDING' && (
              <p className="callout callout-warning">
                Your registration is awaiting Government approval. Browsing lots and placing bids are disabled
                until an admin approves your recycler account.
              </p>
            )}
            {profile.status === 'REJECTED' && (
              <p className="callout callout-danger">
                Your registration was rejected by the Government Admin. Please contact them for details.
              </p>
            )}
          </Card>

          {approved && (
            <>
              {overview && (
                <div className="stat-grid">
                  <div className="stat-tile">
                    <div className="value">{overview.openLots}</div>
                    <div className="label">Lots open for bidding</div>
                  </div>
                  <div className="stat-tile">
                    <div className="value">{countBids('PLACED')}</div>
                    <div className="label">Bids awaiting decision</div>
                  </div>
                  <div className="stat-tile">
                    <div className="value">{countBids('ACCEPTED')}</div>
                    <div className="label">Bids approved</div>
                  </div>
                  <div className="stat-tile">
                    <div className="value">{countBids('REJECTED')}</div>
                    <div className="label">Bids not approved</div>
                  </div>
                </div>
              )}
              <div className="quick-links">
                <Link to="/lots">
                  Browse Available Lots
                  <span>See every lot open for bidding, with ML price estimates.</span>
                </Link>
                <Link to="/my-bids">
                  My Bids
                  <span>Track your bids and whether they were approved.</span>
                </Link>
              </div>
            </>
          )}
        </>
      )}
    </Layout>
  )
}
