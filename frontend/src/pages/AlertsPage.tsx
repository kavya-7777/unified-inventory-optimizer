import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Field'
import { EmptyState, ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { formatDateTime } from '@/lib/utils'
import type { BadgeTone } from '@/lib/utils'

const SEVERITY_TONE: Record<string, BadgeTone> = {
  CRITICAL: 'danger',
  WARNING: 'warn',
  INFO: 'brand',
}

type Filter = 'unresolved' | 'resolved' | 'all'

function ResolveButton({ alertId }: { alertId: number }) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => api.resolveAlert(alertId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  })

  return (
    <Button variant="secondary" size="sm" loading={mutation.isPending} onClick={() => mutation.mutate()}>
      <CheckCircle2 className="h-3.5 w-3.5" /> Resolve
    </Button>
  )
}

export function AlertsPage() {
  const [filter, setFilter] = useState<Filter>('unresolved')
  const [limit, setLimit] = useState(50)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['alerts', filter, limit],
    queryFn: () =>
      api.listAlerts({
        resolved: filter === 'all' ? undefined : filter === 'resolved',
        limit,
      }),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Alerts</h1>
          <p className="mt-1 text-sm text-muted">
            Capacity violations and infeasible transportation flows raised by pipeline runs.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select className="w-36" value={filter} onChange={(e) => setFilter(e.target.value as Filter)}>
            <option value="unresolved">Unresolved</option>
            <option value="resolved">Resolved</option>
            <option value="all">All</option>
          </Select>
          <Select className="w-28" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            {[25, 50, 100, 200].map((n) => (
              <option key={n} value={n}>
                Last {n}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader title="Alerts" />
        <CardBody className="p-0">
          {isLoading && <Spinner />}
          {isError && (
            <div className="p-5">
              <ErrorNotice message={error instanceof ApiError ? error.message : 'Failed to load alerts'} />
            </div>
          )}
          {data && data.length === 0 && (
            <EmptyState
              title={filter === 'unresolved' ? 'No unresolved alerts' : 'No alerts'}
              description="Alerts are raised automatically when a pipeline run hits a capacity violation or an infeasible transportation flow."
            />
          )}
          {data && data.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-2.5 font-medium">Severity</th>
                  <th className="px-5 py-2.5 font-medium">Type</th>
                  <th className="px-5 py-2.5 font-medium">Message</th>
                  <th className="px-5 py-2.5 font-medium">Run</th>
                  <th className="px-5 py-2.5 font-medium">Created</th>
                  <th className="px-5 py-2.5 font-medium" />
                </tr>
              </thead>
              <tbody>
                {data.map((alert) => (
                  <tr key={alert.id} className="border-b border-border last:border-0 hover:bg-slate-50">
                    <td className="px-5 py-2.5">
                      <Badge tone={SEVERITY_TONE[alert.severity] ?? 'neutral'}>{alert.severity}</Badge>
                    </td>
                    <td className="px-5 py-2.5 text-muted">{alert.alert_type}</td>
                    <td className="px-5 py-2.5 text-slate-900">{alert.message}</td>
                    <td className="px-5 py-2.5">
                      {alert.pipeline_run_id ? (
                        <Link to={`/runs/${alert.pipeline_run_id}`} className="font-mono text-xs text-brand-600 hover:underline">
                          {alert.pipeline_run_id.slice(0, 8)}…
                        </Link>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="px-5 py-2.5 text-muted">{formatDateTime(alert.created_at)}</td>
                    <td className="px-5 py-2.5 text-right">
                      {!alert.resolved && <ResolveButton alertId={alert.id} />}
                      {alert.resolved && <Badge tone="ok">Resolved</Badge>}
                    </td>
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
