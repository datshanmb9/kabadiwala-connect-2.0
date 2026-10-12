import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api/apiClient'
import { Brand } from '../components/Layout'
import { InlineErrorBanner } from '../components/StateViews'
import { useAuth } from '../features/auth/AuthContext'
import { recyclerRepository } from '../features/recycler/recyclerRepository'

export function RegisterPage() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitError(null)
    setSubmitting(true)
    try {
      await recyclerRepository.register({ username, password, companyName })
      const loggedIn = await login(username, password)
      if (loggedIn) {
        navigate('/', { replace: true })
      } else {
        setSubmitError('Registered successfully, but automatic login failed. Please log in manually.')
      }
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
    <div className="centered-form">
      <Brand />
      <h1>Register as a Recycler</h1>
      <p className="hint">
        Your account will be created immediately, but every action here requires Government approval first — you
        can log in right away to check your status.
      </p>
      <form onSubmit={handleSubmit}>
        {submitError && <InlineErrorBanner message={submitError} />}

        <label>
          Company name
          <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
        </label>

        <hr />

        <label>
          License ID (this becomes your login username)
          <input value={username} onChange={(e) => setUsername(e.target.value)} required minLength={3} />
        </label>
        <label>
          Choose a password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
          />
        </label>

        <button type="submit" disabled={submitting}>
          {submitting ? 'Registering…' : 'Register'}
        </button>
      </form>
    </div>
    </div>
  )
}
