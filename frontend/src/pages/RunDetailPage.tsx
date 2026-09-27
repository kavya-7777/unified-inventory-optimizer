import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/Badge'
import { ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { formatDateTime, formatDuration } from '@/lib/utils'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted">{label}</p>
      <div className="mt-0.5 text-sm text-slate-900">{children}</div>
    </div>
  )
}

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.getRun(runId!),
    enabled: !!runId,
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/runs" className="inline-flex items-center gap-1 text-sm text-muted hover:text-slate-800">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to runs
        </Link>
        <h1 className="mt-2 text-xl font-semibold text-slate-900">Run detail</h1>
      </div>

      {isLoading && <Spinner />}
      {isError && <ErrorNotice message={(error as Error).message} />}

      {data && (
        <Card>
          <CardHeader title={data.run_type} description={<span className="font-mono text-xs">{data.id}</span>} />
          <CardBody>
            <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
              <Field label="Status">
                <StatusBadge status={data.status} />
              </Field>
              <Field label="Solver">{data.solver ?? '—'}</Field>
              <Field label="Fallback used">{data.fallback_used ? 'Yes' : 'No'}</Field>
              <Field label="Duration">{formatDuration(data.duration_seconds)}</Field>
              <Field label="Started at">{formatDateTime(data.started_at)}</Field>
              <Field label="Finished at">{formatDateTime(data.finished_at)}</Field>
            </div>
            {data.error && (
              <div className="mt-5">
                <ErrorNotice title="Run error" message={data.error} />
              </div>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  )
}
