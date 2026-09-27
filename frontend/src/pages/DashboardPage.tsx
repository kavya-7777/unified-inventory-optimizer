import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowUpRight, ListTree } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatTile, StatTileGrid } from '@/components/ui/StatTile'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { formatDateTime, formatDuration, formatNumber } from '@/lib/utils'

export function DashboardPage() {
  const locations = useQuery({ queryKey: ['locations', 0, 1000], queryFn: () => api.listLocations(0, 1000) })
  const products = useQuery({ queryKey: ['products', 0, 1000], queryFn: () => api.listProducts(0, 1000) })
  const runs = useQuery({ queryKey: ['runs', 5], queryFn: () => api.listRuns(5) })
  const summary = useQuery({ queryKey: ['dashboard-summary'], queryFn: api.getDashboardSummary })

  const nodeCount = locations.data?.length
  const skuCount = products.data?.length
  const lastRun = summary.data?.last_run

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Multi-Echelon Inventory Optimization</h1>
          <p className="mt-1 text-sm text-muted">
            {nodeCount != null ? `${nodeCount} nodes` : '— nodes'} · {skuCount != null ? `${skuCount} SKUs` : '— SKUs'} · Guaranteed-service network
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-xs font-medium text-muted">Open alerts</p>
            <p className={summary.data && summary.data.open_alerts > 0 ? 'text-lg font-bold text-danger-600' : 'text-lg font-bold text-slate-900'}>
              {summary.data ? summary.data.open_alerts : '—'}
            </p>
          </div>
          <Link to="/optimization">
            <Button size="sm">
              Run pipeline <ArrowUpRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      </div>

      <PageHeader
        eyebrow="Control tower"
        title="Network position"
        description="Guaranteed-service model output across suppliers, distribution centers and stores, refreshed by the nightly optimization pipeline."
        badges={
          <>
            {lastRun && <Badge tone={lastRun.status === 'success' ? 'ok' : 'danger'}>LAST RUN {lastRun.status.toUpperCase()}</Badge>}
            {lastRun?.fallback_used && <Badge tone="warn">LP FALLBACK</Badge>}
            <Link to="/runs">
              <Badge tone="neutral">RUN HISTORY</Badge>
            </Link>
          </>
        }
      />

      {summary.isLoading && <Spinner />}
      {summary.isError && (
        <ErrorNotice message={summary.error instanceof ApiError ? summary.error.message : 'Failed to load dashboard summary'} />
      )}

      {summary.data && (
        <StatTileGrid>
          <StatTile
            label="Inventory value"
            value={`$${formatNumber(summary.data.inventory_value / 1_000_000, 2)}M`}
            caption="on hand, at unit cost"
          />
          <StatTile
            label="Avg service level"
            value={summary.data.avg_service_level != null ? formatNumber(summary.data.avg_service_level * 100, 1) : '—'}
            unit="%"
            caption="policy-weighted target"
          />
          <StatTile
            label="Fill rate"
            value={summary.data.fill_rate != null ? formatNumber(summary.data.fill_rate * 100, 1) : '—'}
            unit="%"
            caption="node-SKU pairs above safety stock"
          />
          <StatTile
            label="At risk"
            value={String(summary.data.at_risk_count)}
            caption={`of ${summary.data.measured_pairs} node-SKU pairs`}
            tone={summary.data.at_risk_count > 0 ? 'warn' : 'default'}
          />
          <StatTile
            label="Open alerts"
            value={String(summary.data.open_alerts)}
            tone={summary.data.open_alerts > 0 ? 'danger' : 'default'}
          />
        </StatTileGrid>
      )}

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
