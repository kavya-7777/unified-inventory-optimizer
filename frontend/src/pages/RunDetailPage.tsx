import { useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'
import { RunSummaryPanel } from '@/components/RunSummaryPanel'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Field'
import { EmptyState, ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { formatDateTime, formatDuration, formatNumber, humanize } from '@/lib/utils'

const PAGE_SIZE = 50

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted">{label}</p>
      <div className="mt-0.5 text-sm text-slate-900">{children}</div>
    </div>
  )
}

function ResultsTable({ runId }: { runId: string }) {
  const [productId, setProductId] = useState('')
  const [skip, setSkip] = useState(0)
  const products = useQuery({ queryKey: ['products', 0, 1000], queryFn: () => api.listProducts(0, 1000) })
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['run-results', runId, productId, skip],
    queryFn: () => api.getRunResults(runId, { product_id: productId || undefined, skip, limit: PAGE_SIZE }),
    placeholderData: (prev) => prev,
  })

  return (
    <Card>
      <CardHeader
        title="Optimized targets"
        description="Guaranteed-service decisions per node and SKU: S in / S out are the inbound and promised outbound service times (days), T is the net replenishment time the safety stock must cover"
        action={
          <Select
            className="w-64"
            value={productId}
            onChange={(e) => {
              setProductId(e.target.value)
              setSkip(0)
            }}
          >
            <option value="">All SKUs</option>
            {products.data?.map((p) => (
              <option key={p.id} value={p.id}>{p.sku} — {p.name}</option>
            ))}
          </Select>
        }
      />
      <CardBody className="p-0">
        {isLoading && <Spinner />}
        {isError && <div className="p-5"><ErrorNotice message={(error as Error).message} /></div>}
        {data && data.total === 0 && (
          <EmptyState title="No stored results" description="Sandbox runs only store results for nodes mapped to a real location." />
        )}
        {data && data.total > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-2.5 font-medium">Node</th>
                    <th className="px-4 py-2.5 font-medium">SKU</th>
                    <th className="px-4 py-2.5 text-right font-medium">Demand / day</th>
                    <th className="px-4 py-2.5 text-right font-medium">σ</th>
                    <th className="px-4 py-2.5 text-right font-medium">Service</th>
                    <th className="px-4 py-2.5 text-right font-medium">S in</th>
                    <th className="px-4 py-2.5 text-right font-medium">S out</th>
                    <th className="px-4 py-2.5 text-right font-medium">T</th>
                    <th className="px-4 py-2.5 text-right font-medium">Safety stock</th>
                    <th className="px-4 py-2.5 text-right font-medium">Reorder point</th>
                    <th className="px-4 py-2.5 text-right font-medium">EOQ</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={r.id} className="border-b border-border last:border-0 hover:bg-slate-50">
                      <td className="whitespace-nowrap px-4 py-2">
                        {r.location_name ?? r.location_id} {r.location_type && <Badge tone="neutral">{r.location_type}</Badge>}
                      </td>
                      <td className="px-4 py-2 text-muted" title={r.product_name ?? undefined}>{r.sku ?? r.product_id ?? '—'}</td>
                      <td className="px-4 py-2 text-right">{formatNumber(r.demand_mean, 1)}</td>
                      <td className="px-4 py-2 text-right text-muted">{formatNumber(r.demand_std, 1)}</td>
                      <td className="px-4 py-2 text-right text-muted">{r.service_level != null ? `${formatNumber(r.service_level * 100, 0)}%` : '—'}</td>
                      <td className="px-4 py-2 text-right">{r.s_in ?? '—'}</td>
                      <td className="px-4 py-2 text-right">{r.s_out ?? '—'}</td>
                      <td className="px-4 py-2 text-right font-medium">{r.net_replenishment_time ?? '—'}</td>
                      <td className="px-4 py-2 text-right font-medium">{formatNumber(r.safety_stock, 1)}</td>
                      <td className="px-4 py-2 text-right">{formatNumber(r.reorder_point, 1)}</td>
                      <td className="px-4 py-2 text-right text-muted">{formatNumber(r.order_quantity, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-border px-5 py-3 text-xs text-muted">
              <span>Showing {skip + 1}–{skip + data.items.length} of {data.total}</span>
              <div className="flex gap-1.5">
                <Button variant="secondary" size="sm" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}>
                  <ChevronLeft className="h-3.5 w-3.5" /> Prev
                </Button>
                <Button variant="secondary" size="sm" disabled={skip + data.items.length >= data.total} onClick={() => setSkip(skip + PAGE_SIZE)}>
                  Next <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  )
}

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.getRun(runId!),
    enabled: !!runId,
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 2000 : false),
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
        <>
          <Card>
            <CardHeader title={humanize(data.run_type)} description={<span className="font-mono text-xs">{data.id}</span>} />
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
              {data.summary && (
                <div className="mt-5 border-t border-border pt-5">
                  <RunSummaryPanel summary={data.summary} />
                </div>
              )}
            </CardBody>
          </Card>
          {data.status !== 'running' && <ResultsTable runId={data.id} />}
        </>
      )}
    </div>
  )
}
