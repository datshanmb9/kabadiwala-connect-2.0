import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../features/auth/AuthContext'

/** Leaf brand mark shared by the header and the login/register pages. */
export function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z" />
        <path d="M2 21c0-3 1.85-5.36 5.08-6" />
      </svg>
    </span>
  )
}

export function Brand() {
  return (
    <Link to="/" className="brand">
      <BrandMark />
      <span className="brand-text">
        <strong>Kabadiwala Connect</strong>
        <small>Recycler Portal</small>
      </span>
    </Link>
  )
}

/** Recycler-only nav — this app has no route to anything outside the
 * recycler workflow. Action links only render once APPROVED. */
export function Layout({ children, approved = false }: { children: ReactNode; approved?: boolean }) {
  const { session, logout } = useAuth()

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <Brand />
          {session && (
            <nav className="top-nav" aria-label="Recycler navigation">
              <NavLink to="/" end>
                Dashboard
              </NavLink>
              {approved && (
                <>
                  <NavLink to="/lots">Browse Lots</NavLink>
                  <NavLink to="/my-bids">My Bids</NavLink>
                </>
              )}
              <div className="header-user">
                <span>{session.username}</span>
                <button type="button" className="link-button" onClick={() => void logout()}>
                  Logout
                </button>
              </div>
            </nav>
          )}
        </div>
      </header>
      <main className="app-main">{children}</main>
    </div>
  )
}

/** Consistent page title block used by every recycler page. */
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
