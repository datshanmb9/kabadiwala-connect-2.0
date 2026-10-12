import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../features/auth/AuthContext'
import { Icon } from './Icon'

/** Admin navigation. RRR Centres and Lots & Bids are intentionally not
 * listed here (their routes and backend features still exist). */
const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: 'dashboard' },
  { to: '/recyclers', label: 'Recyclers', icon: 'recycler' },
  { to: '/collectors', label: 'Collectors', icon: 'collectors' },
  { to: '/wards', label: 'Wards', icon: 'wards' },
  { to: '/operations', label: 'Operations', icon: 'operations' },
  { to: '/rewards', label: 'Rewards', icon: 'rewards' },
  { to: '/complaints', label: 'Complaints', icon: 'complaints' },
  { to: '/audit-logs', label: 'Audit Logs', icon: 'audit' },
]

/** Government-Admin-only shell — this app has no route to anything outside
 * the admin workflow. */
export function Layout({ children }: { children: ReactNode }) {
  const { session, logout } = useAuth()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-mark">
            <Icon name="leaf" size={20} />
          </span>
          <span className="brand-text">
            <strong>Kabadiwala Connect</strong>
            <small>Government Admin</small>
          </span>
        </Link>
        {session && (
          <>
            <nav className="side-nav" aria-label="Admin navigation">
              <div className="side-nav-label">Administration</div>
              {NAV_ITEMS.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.to === '/'}>
                  <Icon name={item.icon} />
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <div className="sidebar-footer">
              <div className="user-chip">
                <span className="avatar">{session.username.slice(0, 1).toUpperCase()}</span>
                <span>{session.username}</span>
              </div>
              <button type="button" className="link-button" onClick={() => void logout()}>
                Logout
              </button>
            </div>
          </>
        )}
      </aside>
      <div className="app-body">
        <header className="topbar">
          <span className="topbar-title">
            <Icon name="shield" size={16} />
            Government E-Waste Management Portal
          </span>
          <span className="topbar-pill">Kabadiwala Connect 2.0</span>
        </header>
        <main className="app-main">{children}</main>
      </div>
    </div>
  )
}

/** Consistent page title block used by every admin page. */
export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {description && <p className="page-subtitle">{description}</p>}
      </div>
      {actions}
    </div>
  )
}
