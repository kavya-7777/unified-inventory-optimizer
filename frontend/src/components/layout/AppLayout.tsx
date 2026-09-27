import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Boxes,
  Gauge,
  LayoutDashboard,
  LineChart as LineChartIcon,
  ListTree,
  Package,
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/inventory', label: 'Inventory', icon: Package },
  { to: '/demand', label: 'Demand', icon: LineChartIcon },
  { to: '/optimization', label: 'Optimization', icon: Gauge },
  { to: '/runs', label: 'Pipeline Runs', icon: ListTree },
]

function HealthPill() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 15_000,
    retry: 1,
  })

  const ok = !isLoading && !isError && data?.status === 'ok'
  const label = isLoading ? 'Checking…' : ok ? 'Backend online' : 'Backend unreachable'

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border bg-white px-3 py-1 text-xs font-medium text-slate-600">
      <span
        className={cn(
          'h-2 w-2 rounded-full',
          isLoading ? 'bg-slate-300' : ok ? 'bg-ok-600' : 'bg-danger-600',
        )}
      />
      {label}
    </span>
  )
}

export function AppLayout() {
  return (
    <div className="flex min-h-screen bg-bg">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-white px-4 py-5 sm:flex">
        <div className="mb-6 flex items-center gap-2 px-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
            <Boxes className="h-4.5 w-4.5" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight text-slate-900">MEIO Platform</p>
            <p className="text-xs leading-tight text-muted">Inventory optimizer</p>
          </div>
        </div>

        <nav className="flex flex-col gap-0.5">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto px-2 pt-4 text-xs text-muted">
          <p>API: {import.meta.env.VITE_API_URL || 'http://localhost:8000'}</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border bg-white px-6 py-3.5 sm:px-8">
          <p className="text-sm font-medium text-slate-500 sm:hidden">MEIO Platform</p>
          <div className="hidden sm:block" />
          <HealthPill />
        </header>
        <main className="flex-1 px-6 py-6 sm:px-8 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
