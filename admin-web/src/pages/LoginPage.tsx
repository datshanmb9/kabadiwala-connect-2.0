import { type FormEvent, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { Icon } from '../components/Icon'
import { InlineErrorBanner } from '../components/StateViews'
import { useAuth } from '../features/auth/AuthContext'

export function LoginPage() {
  const { status, login, errorMessage } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (status === 'authenticated') {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    await login(username, password)
    setSubmitting(false)
  }

  return (
    <div className="auth-page">
      <aside className="auth-aside">
        <div className="brand">
          <span className="brand-mark">
            <Icon name="leaf" size={20} />
          </span>
          <span className="brand-text">
            <strong>Kabadiwala Connect</strong>
            <small>Government Admin</small>
          </span>
        </div>
        <div>
          <h2>Government E-Waste Management Portal</h2>
          <ul>
            <li>Approve recyclers and manage collectors</li>
            <li>Monitor collections, handovers and wards</li>
            <li>Oversee rewards, complaints and audit trails</li>
          </ul>
        </div>
        <p className="hint" style={{ color: '#9fb2c9' }}>
          Kabadiwala Connect 2.0
        </p>
      </aside>
      <div className="centered-form">
        <h1>Government Admin Login</h1>
        <p className="page-subtitle" style={{ marginBottom: 24 }}>
          Sign in with your administrator credentials.
        </p>
        <form onSubmit={handleSubmit}>
          {errorMessage && <InlineErrorBanner message={errorMessage} />}
          <label>
            Username
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={3}
              autoComplete="username"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete="current-password"
            />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? 'Logging in…' : 'Log In'}
          </button>
        </form>
        <p className="hint">Admin accounts are provisioned by the seed script — there is no self-registration.</p>
      </div>
    </div>
  )
}
