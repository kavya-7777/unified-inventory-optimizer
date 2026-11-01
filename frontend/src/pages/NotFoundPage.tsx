import { Link, useLocation } from 'react-router-dom'
import { Compass } from 'lucide-react'

export function NotFoundPage() {
  const location = useLocation()
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 py-16 text-center">
      <Compass className="h-10 w-10 text-slate-300" />
      <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">404</p>
      <h1 className="text-lg font-semibold text-slate-900">Page not found</h1>
      <p className="text-sm text-muted">
        There’s nothing at <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{location.pathname}</code>. It may
        have moved, or the link may be mistyped.
      </p>
      <Link to="/" className="text-sm font-medium text-brand-600 hover:text-brand-700">
        Go to the dashboard
      </Link>
    </div>
  )
}
