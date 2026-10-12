import { type FormEvent, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Brand } from '../components/Layout'
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
      <div className="centered-form">
        <Brand />
        <h1>Recycler Login</h1>
        <p className="page-subtitle" style={{ marginBottom: 24 }}>
          Browse listed e-waste lots and manage your bids.
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
        <p>
          Don't have an account? <Link to="/register">Register as a Recycler</Link>
        </p>
      </div>
    </div>
  )
}
