import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  Boxes,
  ChevronDown,
  FileSpreadsheet,
  Gauge,
  History,
  KeyRound,
  LayoutDashboard,
  LineChart as LineChartIcon,
  ListTree,
  Loader2,
  LogOut,
  Menu,
  Package,
  SlidersHorizontal,
  Truck,
  Users,
  Waypoints,
  X,
} from 'lucide-react'
import { api, subscribeServerState, type ServerState } from '@/lib/api'
import { ROLE_LABEL, useAuth } from '@/lib/auth-context'
import type { Role } from '@/lib/types'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'

type NavItem = { to: string; label: string; icon: typeof LayoutDashboard; end?: boolean; role?: Role }

const NAV_SECTIONS: { title?: string; items: NavItem[] }[] = [
  {
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
      { to: '/network', label: 'Network', icon: Waypoints },
      { to: '/inventory', label: 'Inventory', icon: Package },
      { to: '/demand', label: 'Demand & Forecast', icon: LineChartIcon },
      { to: '/optimization', label: 'Optimization', icon: Gauge, role: 'planner' },
      { to: '/transportation', label: 'Transportation', icon: Truck },
      { to: '/runs', label: 'Pipeline Runs', icon: ListTree },
      { to: '/policies', label: 'Policies', icon: SlidersHorizontal },
      { to: '/alerts', label: 'Alerts', icon: AlertTriangle },
    ],
  },
  {
    title: 'Data',
    items: [{ to: '/import', label: 'Data Import', icon: FileSpreadsheet, role: 'planner' }],
  },
  {
    title: 'Admin',
    items: [
      { to: '/users', label: 'Users', icon: Users, role: 'admin' },
      { to: '/activity', label: 'Activity log', icon: History, role: 'admin' },
    ],
  },
]

function useServerState(): ServerState {
  const [state, setState] = useState<ServerState>('ok')
  useEffect(() => subscribeServerState(setState), [])
  return state
}

function HealthPill() {
  const server = useServerState()
  const { data, isError, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: 1,
  })

  const waking = server === 'waking'
  const ok = !waking && !isLoading && !isError && data?.status === 'ok'
  const label = waking ? 'Waking up server…' : isLoading ? 'Checking…' : ok ? 'Online' : 'Server unreachable'

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border bg-white px-3 py-1 text-xs font-medium text-slate-600">
      <span
        className={cn(
          'h-2 w-2 rounded-full',
          waking ? 'animate-pulse bg-warn-600' : isLoading ? 'bg-slate-300' : ok ? 'bg-ok-600' : 'bg-danger-600',
        )}
      />
      <span className="hidden sm:inline">{label}</span>
    </span>
  )
}

function WakingBanner() {
  const server = useServerState()
  if (server !== 'waking') return null
  return (
    <div className="flex items-center gap-2 border-b border-warn-600/20 bg-warn-50 px-4 py-2 text-sm text-warn-700 sm:px-8">
      <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
      The server is waking up after being idle. This can take up to a minute; your request will continue
      automatically.
    </div>
  )
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth()
  return (
    <nav className="flex flex-col gap-4">
      {NAV_SECTIONS.map((section, i) => {
        const items = section.items.filter((item) => !item.role || can(item.role))
        if (items.length === 0) return null
        return (
          <div key={section.title ?? i} className="flex flex-col gap-0.5">
            {section.title && (
              <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{section.title}</p>
            )}
            {items.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={onNavigate}
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
          </div>
        )
      })}
    </nav>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-2 px-2">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white">
        <Boxes className="h-4.5 w-4.5" />
      </div>
      <div>
        <p className="text-sm font-semibold leading-tight text-slate-900">Unified Inventory Optimizer</p>
        <p className="text-xs leading-tight text-muted">Inventory optimizer</p>
      </div>
    </div>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!user) return null
  const initials = user.name
    .split(/\s+/)
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-lg px-2 py-1 text-left hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
          {initials}
        </span>
        <span className="hidden min-w-0 md:block">
          <span className="block max-w-40 truncate text-sm font-medium text-slate-900">{user.name}</span>
          <span className="block text-xs text-muted">{ROLE_LABEL[user.role]}</span>
        </span>
        <ChevronDown className="h-4 w-4 text-slate-400" />
      </button>
      {open && (
        <div role="menu" className="card absolute right-0 z-30 mt-2 w-64 p-1.5 shadow-lg">
          <div className="border-b border-border px-3 pb-2.5 pt-1.5">
            <p className="truncate text-sm font-medium text-slate-900">{user.name}</p>
            <p className="truncate text-xs text-muted">{user.email}</p>
            <Badge tone="brand" className="mt-1.5">{ROLE_LABEL[user.role]}</Badge>
          </div>
          <Link
            to="/account"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="mt-1 flex items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            <KeyRound className="h-4 w-4" /> Account & password
          </Link>
          <button
            type="button"
            role="menuitem"
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      )}
    </div>
  )
}

export function AppLayout() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()

  // Close the phone menu whenever the page changes.
  useEffect(() => setDrawerOpen(false), [location.pathname])

  useEffect(() => {
    if (!drawerOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setDrawerOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [drawerOpen])

  return (
    <div className="flex min-h-screen bg-bg">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col overflow-y-auto border-r border-border bg-white px-4 py-5 lg:flex">
        <div className="mb-6">
          <Brand />
        </div>
        <NavLinks />
      </aside>

      {/* Phone / tablet navigation */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0 bg-slate-900/40"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="relative flex h-full w-72 max-w-[85vw] flex-col overflow-y-auto bg-white px-4 py-5 shadow-xl">
            <div className="mb-6 flex items-center justify-between">
              <Brand />
              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setDrawerOpen(false)}
                className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <NavLinks onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-border bg-white px-4 py-2.5 sm:px-8">
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              aria-label="Open menu"
              onClick={() => setDrawerOpen(true)}
              className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 lg:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
            <p className="truncate text-sm font-semibold text-slate-900 lg:hidden">Unified Inventory Optimizer</p>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <HealthPill />
            <UserMenu />
          </div>
        </header>
        <WakingBanner />
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
