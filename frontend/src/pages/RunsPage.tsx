import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/Badge'
import { ErrorNotice, EmptyState, Spinner } from '@/components/ui/Feedback'
import { Select } from '@/components/ui/Field'
import { formatDateTime, formatDuration } from '@/lib/utils'

export function RunsPage() {
  const [limit, setLimit] = useState(10)
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['runs', limit],
    queryFn: () => api.listRuns(limit),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Pipeline runs</h1>
          <p className="mt-1 text-sm text-muted">History of optimization and pipeline executions.</p>
        </div>
        <Select className="w-32" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
          {[10, 25, 50, 100].map((n) => (
            <option key={n} value={n}>
              Last {n}
            </option>
          ))}
        </Select>
      </div>

      <Card>
        <CardHeader title="Runs" />
        <CardBody className="p-0">
          {isLoading && <Spinner />}
          {isError && <div className="p-5"><ErrorNotice message={(error as Error).message} /></div>}
          {data && data.length === 0 && <EmptyState title="No runs yet" description="Trigger one from the Optimization page." />}
          {data && data.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-2.5 font-medium">Run type</th>
                  <th className="px-5 py-2.5 font-medium">Status</th>
                  <th className="px-5 py-2.5 font-medium">Solver</th>
                  <th className="px-5 py-2.5 font-medium">Fallback</th>
                  <th className="px-5 py-2.5 font-medium">Started</th>
                  <th className="px-5 py-2.5 font-medium">Duration</th>
                </tr>
              </thead>
              <tbody>
                {data.map((run) => (
                  <tr key={run.id} className="border-b border-border last:border-0 hover:bg-slate-50">
                    <td className="px-5 py-2.5">
                      <Link to={`/runs/${run.id}`} className="font-medium text-brand-600 hover:underline">
                        {run.run_type}
                      </Link>
                    </td>
                    <td className="px-5 py-2.5"><StatusBadge status={run.status} /></td>
                    <td className="px-5 py-2.5 text-muted">{run.solver ?? '—'}</td>
                    <td className="px-5 py-2.5 text-muted">{run.fallback_used ? 'yes' : 'no'}</td>
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
