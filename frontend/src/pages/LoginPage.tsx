import { useEffect, useState, type SubmitEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Boxes, Loader2, LogIn } from 'lucide-react'
import { ApiError, subscribeServerState, type ServerState } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { Button } from '@/components/ui/Button'
import { Input, Label } from '@/components/ui/Field'
import { ErrorNotice } from '@/components/ui/Feedback'

export function LoginPage() {
  const { status, login, sessionExpired } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [server, setServer] = useState<ServerState>('ok')

  useEffect(() => subscribeServerState(setServer), [])

  if (status === 'signed-in') return <Navigate to={from} replace />

  async function onSubmit(e: SubmitEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sign-in failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Boxes className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Unified Inventory Optimizer</h1>
            <p className="mt-1 text-sm text-muted">Sign in to plan inventory across your network</p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="card flex flex-col gap-4 p-6" noValidate>
          {sessionExpired && !error && (
            <p className="rounded-lg bg-warn-50 px-3 py-2 text-sm text-warn-700">
              Your session expired. Please sign in again.
            </p>
          )}
          {error && <ErrorNotice title="Couldn’t sign in" message={error} />}

          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <Button type="submit" loading={submitting} disabled={!email || !password}>
            {!submitting && <LogIn className="h-4 w-4" />}
            Sign in
          </Button>

          {submitting && server === 'waking' && (
            <p className="flex items-start gap-2 text-xs text-muted">
              <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin" />
              The server is waking up after being idle. This can take up to a minute the first time.
            </p>
          )}
        </form>

        <p className="mt-4 text-center text-xs text-muted">
          No account? Ask your administrator to create one for you.
        </p>
      </div>
    </div>
  )
}
