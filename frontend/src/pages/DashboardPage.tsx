import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AlertTriangle, Gauge, LineChart, ListTree, Package } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/Badge'
import { ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { formatDateTime, formatDuration } from '@/lib/utils'

function StatCard({
  label,
  value,
  icon: Icon,
  to,
  tone = 'brand',
}: {
  label: string
  value: string
  icon: typeof Package
  to: string
  tone?: 'brand' | 'danger'
}) {
  return (
    <Link to={to} className="card flex items-center gap-4 px-5 py-4 transition-shadow hover:shadow-sm">
      <div
        className={cn(
          'flex h-10 w-10 items-center justify-center rounded-lg',
          tone === 'danger' ? 'bg-danger-50 text-danger-600' : 'bg-brand-50 text-brand-600',
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-xs font-medium text-muted">{label}</p>
        <p className="text-lg font-semibold text-slate-900">{value}</p>
      </div>
    </Link>
  )
}

export function DashboardPage() {
  const locations = useQuery({ queryKey: ['locations', 0, 100], queryFn: () => api.listLocations(0, 100) })
  const products = useQuery({ queryKey: ['products', 0, 100], queryFn: () => api.listProducts(0, 100) })
  const runs = useQuery({ queryKey: ['runs', 5], queryFn: () => api.listRuns(5) })
  const alerts = useQuery({
    queryKey: ['alerts', 'unresolved', 100],
    queryFn: () => api.listAlerts({ resolved: false, limit: 100 }),
  })

  const countLabel = (q: UseQueryResult<unknown[], Error>) =>
    q.isLoading ? '…' : q.isError ? '—' : `${q.data!.length}${q.data!.length === 100 ? '+' : ''}`

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-muted">
          Overview of your multi-echelon inventory optimization (MEIO) platform.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Locations" value={countLabel(locations)} icon={Package} to="/inventory" />
        <StatCard label="Products" value={countLabel(products)} icon={Package} to="/inventory" />
        <StatCard label="Demand history" value="Explore" icon={LineChart} to="/demand" />
        <StatCard label="Run optimization" value="GSM · Forecast · Pipeline" icon={Gauge} to="/optimization" />
        <StatCard
          label="Unresolved alerts"
          value={countLabel(alerts)}
          icon={AlertTriangle}
          to="/alerts"
          tone={alerts.data && alerts.data.length > 0 ? 'danger' : 'brand'}
        />
      </div>

      <Card>
        <CardHeader
          title="Recent pipeline runs"
          description="Latest optimization and pipeline executions"
          action={
            <Link to="/runs" className="flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700">
              View all <ListTree className="h-3.5 w-3.5" />
            </Link>
          }
        />
        <CardBody className="p-0">
          {runs.isLoading && <Spinner />}
          {runs.isError && <div className="p-5"><ErrorNotice message={(runs.error as Error).message} /></div>}
          {runs.data && runs.data.length === 0 && (
            <p className="px-5 py-8 text-center text-sm text-muted">
              No pipeline runs yet — trigger one from the Optimization page.
            </p>
          )}
          {runs.data && runs.data.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-2.5 font-medium">Run type</th>
                  <th className="px-5 py-2.5 font-medium">Status</th>
                  <th className="px-5 py-2.5 font-medium">Solver</th>
                  <th className="px-5 py-2.5 font-medium">Started</th>
                  <th className="px-5 py-2.5 font-medium">Duration</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.map((run) => (
                  <tr key={run.id} className="border-b border-border last:border-0 hover:bg-slate-50">
                    <td className="px-5 py-2.5">
                      <Link to={`/runs/${run.id}`} className="font-medium text-brand-600 hover:underline">
                        {run.run_type}
                      </Link>
                    </td>
                    <td className="px-5 py-2.5"><StatusBadge status={run.status} /></td>
                    <td className="px-5 py-2.5 text-muted">{run.solver ?? '—'}</td>
                    <td className="px-5 py-2.5 text-muted">{formatDateTime(run.started_at)}</td>
                    <td className="px-5 py-2.5 text-muted">{formatDuration(run.duration_seconds)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
