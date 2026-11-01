import type { ReactNode } from 'react'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import { Loader2, ShieldAlert } from 'lucide-react'
import { ROLE_LABEL, useAuth } from '@/lib/auth-context'
import type { Role } from '@/lib/types'

/** Sends signed-out visitors to /login, remembering where they were going. */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center gap-2 bg-bg text-sm text-muted">
        <Loader2 className="h-4 w-4 animate-spin" />
        Signing you in…
      </div>
    )
  }
  if (status === 'signed-out') {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}

/** Shows the page only to users with at least `role`; others get an explanation. */
export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { can, user } = useAuth()
  if (can(role)) return <>{children}</>
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 py-16 text-center">
      <ShieldAlert className="h-10 w-10 text-slate-300" />
      <h1 className="text-lg font-semibold text-slate-900">You don’t have access to this page</h1>
      <p className="text-sm text-muted">
        It needs the {ROLE_LABEL[role]} role{role !== 'admin' ? ' or higher' : ''}. You’re signed in as{' '}
        {user ? ROLE_LABEL[user.role] : 'a guest'}. Ask an admin if you need access.
      </p>
      <Link to="/" className="text-sm font-medium text-brand-600 hover:text-brand-700">
        Back to the dashboard
      </Link>
    </div>
  )
}
