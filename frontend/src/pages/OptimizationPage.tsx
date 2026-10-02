import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Play } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { RunSummaryPanel } from '@/components/RunSummaryPanel'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { FormRow, Input, Select, Textarea } from '@/components/ui/Field'
import { ErrorNotice } from '@/components/ui/Feedback'
import { StatusBadge } from '@/components/ui/Badge'
import { Tabs } from '@/components/ui/Tabs'
import { formatDuration, formatNumber } from '@/lib/utils'
import type {
  ForecastRunResponse,
  OptimizationRunResponse,
  PipelineRunResult,
} from '@/lib/types'

const DEMO_NODES = [
  { id: 'Supplier', type: 'Supplier', processing_time: 2, holding_cost: 1.0 },
  { id: 'DC1', type: 'DC', processing_time: 1, holding_cost: 2.0 },
  { id: 'Store1', type: 'Store', processing_time: 0, holding_cost: 5.0, demand_std: 10.0 },
]

const DEMO_EDGES = [
  { source: 'Supplier', target: 'DC1', transit_time: 3, cost_per_unit: 2.5, capacity: 1000 },
  { source: 'DC1', target: 'Store1', transit_time: 1, cost_per_unit: 5.0, capacity: 500 },
]

const DEMO_ITEMS_HISTORY = [{ id: 'Store1', history: [100.0, 110.0, 90.0, 105.0, 100.0, 110.0] }]

function parseJson<T>(text: string, fallback: T): T {
  const trimmed = text.trim()
  if (!trimmed) return fallback
  return JSON.parse(trimmed) as T
}

function JsonField({ label, value, onChange, rows = 8 }: { label: string; value: string; onChange: (v: string) => void; rows?: number }) {
  return (
    <FormRow label={label} hint="JSON — leave empty to use the backend default demo network">
      <Textarea rows={rows} value={value} onChange={(e) => onChange(e.target.value)} spellCheck={false} />
    </FormRow>
  )
}

const INVALIDATE_AFTER_RUN = ['dashboard-summary', 'inventory-positions', 'alerts', 'runs', 'transportation-plan']

function NetworkRunner() {
  const queryClient = useQueryClient()
  const products = useQuery({ queryKey: ['products', 0, 1000], queryFn: () => api.listProducts(0, 1000) })
  const [productId, setProductId] = useState('')
  const [horizon, setHorizon] = useState(14)
  const [historyDays, setHistoryDays] = useState(90)
  const [maxServiceTime, setMaxServiceTime] = useState(30)
  const [runId, setRunId] = useState<string | null>(null)

  const start = useMutation({
    mutationFn: () =>
      api.runNetwork({
        product_ids: productId ? [productId] : null,
        horizon,
        history_days: historyDays,
        max_service_time: maxServiceTime,
      }),
    onSuccess: (data) => setRunId(data.pipeline_run_id),
    onError: (err) => {
      // 409: another run is in progress — follow that one instead.
      const body = err instanceof ApiError ? (err.details as { detail?: { pipeline_run_id?: string } }) : null
      if (body?.detail?.pipeline_run_id) setRunId(body.detail.pipeline_run_id)
    },
  })

  const run = useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.getRun(runId!),
    enabled: !!runId,
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 1500 : false),
  })

  const status = run.data?.status
  useEffect(() => {
    if (status && status !== 'running') {
      for (const key of INVALIDATE_AFTER_RUN) queryClient.invalidateQueries({ queryKey: [key] })
    }
  }, [status, queryClient])

  const running = start.isPending || status === 'running'

  return (
    <Card>
      <CardHeader
        title="Network run"
        description="Uses the data in the database: forecasts every store × SKU, rolls demand up to DCs and suppliers, solves the guaranteed-service model per SKU, then flags stockout risks and plans lane flows."
      />
      <CardBody>
        <div className="flex flex-wrap items-end gap-3">
          <FormRow label="SKUs">
            <Select className="w-64" value={productId} onChange={(e) => setProductId(e.target.value)}>
              <option value="">All SKUs</option>
              {products.data?.map((p) => (
                <option key={p.id} value={p.id}>{p.sku} — {p.name}</option>
              ))}
            </Select>
          </FormRow>
          <FormRow label="Forecast horizon (days)">
            <Input type="number" min={1} max={90} className="w-32" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} />
          </FormRow>
          <FormRow label="History window (days)">
            <Input type="number" min={28} max={730} className="w-32" value={historyDays} onChange={(e) => setHistoryDays(Number(e.target.value))} />
          </FormRow>
          <FormRow label="Max service time (days)">
            <Input type="number" min={1} max={365} className="w-32" value={maxServiceTime} onChange={(e) => setMaxServiceTime(Number(e.target.value))} />
          </FormRow>
          <Button onClick={() => start.mutate()} loading={running} disabled={running}>
            <Play className="h-3.5 w-3.5" /> Run network pipeline
          </Button>
        </div>

        {start.isError && (
          <div className="mt-4">
            <ErrorNotice message={start.error instanceof ApiError ? start.error.message : 'Could not start the run'} />
          </div>
        )}

        {run.data && (
          <div className="mt-5 border-t border-border pt-5">
            <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
              <StatusBadge status={run.data.status} />
              {status === 'running' && <span className="text-muted">Forecasting and optimizing…</span>}
              {run.data.duration_seconds != null && <span className="text-muted">{formatDuration(run.data.duration_seconds)}</span>}
              <Link to={`/runs/${run.data.id}`} className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline">
                Open run details <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>
            {run.data.error && <ErrorNotice title="Run failed" message={run.data.error} />}
            {run.data.summary && <RunSummaryPanel summary={run.data.summary} />}
          </div>
        )}
      </CardBody>
    </Card>
  )
}

function GsmRunner() {
  const [nodes, setNodes] = useState(JSON.stringify(DEMO_NODES, null, 2))
  const [edges, setEdges] = useState(JSON.stringify(DEMO_EDGES, null, 2))
  const [maxServiceTime, setMaxServiceTime] = useState(30)
  const [parseError, setParseError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      api.runOptimization({
        run_type: 'manual',
        nodes: parseJson(nodes, null),
        edges: parseJson(edges, null),
        max_service_time: maxServiceTime,
      }),
  })

  const run = () => {
    setParseError(null)
    try {
      mutation.mutate()
    } catch (e) {
      setParseError(e instanceof Error ? e.message : 'Invalid JSON')
    }
  }

  const result = mutation.data as OptimizationRunResponse | undefined

  return (
    <Card>
      <CardHeader title="GSM optimization" description="Guaranteed Service Model — solves for stock levels across the network" />
      <CardBody>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <JsonField label="Nodes" value={nodes} onChange={setNodes} />
          <JsonField label="Edges" value={edges} onChange={setEdges} rows={5} />
        </div>
        <div className="mt-4 flex items-end gap-3">
          <FormRow label="Max service time (days)">
            <Input
              type="number"
              className="w-40"
              value={maxServiceTime}
              onChange={(e) => setMaxServiceTime(Number(e.target.value))}
            />
          </FormRow>
          <Button onClick={run} loading={mutation.isPending}>
            <Play className="h-3.5 w-3.5" /> Run optimization
          </Button>
        </div>

        {parseError && <div className="mt-4"><ErrorNotice title="Invalid JSON" message={parseError} /></div>}
        {mutation.isError && (
          <div className="mt-4">
            <ErrorNotice message={mutation.error instanceof ApiError ? mutation.error.message : 'Optimization run failed'} />
          </div>
        )}

        {result && (
          <div className="mt-5 border-t border-border pt-5">
            <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
              <StatusBadge status={result.status} />
              {result.solver && <span className="text-muted">solver: {result.solver}</span>}
              {result.fallback_used && <span className="text-warn-700">fallback used</span>}
              {result.total_duration_seconds != null && (
                <span className="text-muted">{formatDuration(result.total_duration_seconds)}</span>
              )}
              <span className="font-mono text-xs text-slate-400">{result.pipeline_run_id}</span>
            </div>

            {result.errors && result.errors.length > 0 && (
              <ErrorNotice title="Validation errors" message={result.errors.join('; ')} />
            )}

            {result.node_results && Object.keys(result.node_results).length > 0 && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="py-2 pr-4 font-medium">Node</th>
                    <th className="py-2 pr-4 font-medium">S in</th>
                    <th className="py-2 pr-4 font-medium">S out</th>
                    <th className="py-2 pr-4 font-medium">Net replenishment time</th>
                    <th className="py-2 pr-4 font-medium">Safety stock</th>
                    <th className="py-2 pr-4 font-medium">Reorder point</th>
                    <th className="py-2 pr-4 font-medium">Order qty (EOQ)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.node_results).map(([nodeId, r]) => (
                    <tr key={nodeId} className="border-b border-border last:border-0">
                      <td className="py-1.5 pr-4 font-medium text-slate-900">{nodeId}</td>
                      <td className="py-1.5 pr-4">{r.s_in}</td>
                      <td className="py-1.5 pr-4">{r.s_out}</td>
                      <td className="py-1.5 pr-4">{r.net_replenishment_time}</td>
                      <td className="py-1.5 pr-4">{formatNumber(r.safety_stock, 1)}</td>
                      <td className="py-1.5 pr-4">{formatNumber(r.reorder_point, 1)}</td>
                      <td className="py-1.5 pr-4">{formatNumber(r.order_quantity, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  )
}

function ForecastRunner() {
  const [items, setItems] = useState(JSON.stringify(DEMO_ITEMS_HISTORY, null, 2))
  const [horizon, setHorizon] = useState(4)

  const mutation = useMutation({
    mutationFn: () =>
      api.runForecast({
        items: parseJson(items, []),
        horizon,
      }),
  })

  const result = mutation.data as ForecastRunResponse | undefined

  return (
    <Card>
      <CardHeader title="Demand forecast" description="Automatic model selection on your own series — nothing is saved" />
      <CardBody>
        <JsonField label="Items history" value={items} onChange={setItems} rows={6} />
        <div className="mt-4 flex items-end gap-3">
          <FormRow label="Horizon (periods)">
            <Input type="number" className="w-40" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} />
          </FormRow>
          <Button onClick={() => mutation.mutate()} loading={mutation.isPending}>
            <Play className="h-3.5 w-3.5" /> Run forecast
          </Button>
        </div>

        {mutation.isError && (
          <div className="mt-4">
            <ErrorNotice message={mutation.error instanceof ApiError ? mutation.error.message : 'Forecast run failed'} />
          </div>
        )}

        {result && (
          <div className="mt-5 border-t border-border pt-5">
            <p className="mb-3 text-sm text-muted">{result.count} item(s) forecast</p>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                  <th className="py-2 pr-4 font-medium">Item</th>
                  <th className="py-2 pr-4 font-medium">Pattern</th>
                  <th className="py-2 pr-4 font-medium">Method</th>
                  <th className="py-2 pr-4 font-medium">MASE</th>
                  <th className="py-2 pr-4 font-medium">Forecast</th>
                </tr>
              </thead>
              <tbody>
                {result.forecasts.map((f) => (
                  <tr key={f.id} className="border-b border-border last:border-0">
                    <td className="py-1.5 pr-4 font-medium text-slate-900">{f.id}</td>
                    <td className="py-1.5 pr-4">{f.pattern}</td>
                    <td className="py-1.5 pr-4">{f.method}</td>
                    <td className="py-1.5 pr-4">{formatNumber(f.mase, 2)}</td>
                    <td className="py-1.5 pr-4 font-mono text-xs">
                      [{f.forecast.map((v) => formatNumber(v, 1)).join(', ')}]
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  )
}

function PipelineRunner() {
  const [nodes, setNodes] = useState(JSON.stringify(DEMO_NODES, null, 2))
  const [edges, setEdges] = useState(JSON.stringify(DEMO_EDGES, null, 2))
  const [itemsHistory, setItemsHistory] = useState(JSON.stringify(DEMO_ITEMS_HISTORY, null, 2))
  const [horizon, setHorizon] = useState(4)
  const [maxServiceTime, setMaxServiceTime] = useState(30)

  const mutation = useMutation({
    mutationFn: () =>
      api.runPipeline({
        run_type: 'daily_batch',
        nodes: parseJson(nodes, null),
        edges: parseJson(edges, null),
        items_history: parseJson(itemsHistory, null),
        horizon,
        max_service_time: maxServiceTime,
      }),
  })

  const result = mutation.data as PipelineRunResult | undefined

  return (
    <Card>
      <CardHeader title="Full pipeline" description="Forecast → GSM optimization → transportation LP, end to end" />
      <CardBody>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <JsonField label="Nodes" value={nodes} onChange={setNodes} rows={6} />
          <JsonField label="Edges" value={edges} onChange={setEdges} rows={4} />
        </div>
        <div className="mt-4">
          <JsonField label="Items history" value={itemsHistory} onChange={setItemsHistory} rows={3} />
        </div>
        <div className="mt-4 flex items-end gap-3">
          <FormRow label="Horizon">
            <Input type="number" className="w-32" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} />
          </FormRow>
          <FormRow label="Max service time">
            <Input type="number" className="w-32" value={maxServiceTime} onChange={(e) => setMaxServiceTime(Number(e.target.value))} />
          </FormRow>
          <Button onClick={() => mutation.mutate()} loading={mutation.isPending}>
            <Play className="h-3.5 w-3.5" /> Run pipeline
          </Button>
        </div>

        {mutation.isError && (
          <div className="mt-4">
            <ErrorNotice message={mutation.error instanceof ApiError ? mutation.error.message : 'Pipeline run failed'} />
          </div>
        )}

        {result && (
          <div className="mt-5 border-t border-border pt-5">
            <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
              <StatusBadge status={result.status} />
              <span className="font-mono text-xs text-slate-400">{result.pipeline_run_id}</span>
            </div>
            {result.error && <ErrorNotice message={result.error} />}
            {result.stages && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-border p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">Forecast</p>
                  <div className="mt-1.5"><StatusBadge status={result.stages.forecast?.status} /></div>
                  {result.stages.forecast?.count != null && (
                    <p className="mt-1 text-xs text-muted">{result.stages.forecast.count} item(s)</p>
                  )}
                </div>
                <div className="rounded-lg border border-border p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">GSM</p>
                  <div className="mt-1.5"><StatusBadge status={result.stages.gsm?.status} /></div>
                  {result.stages.gsm?.solver && <p className="mt-1 text-xs text-muted">{result.stages.gsm.solver}</p>}
                </div>
                <div className="rounded-lg border border-border p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">Transportation</p>
                  <div className="mt-1.5"><StatusBadge status={result.stages.transportation?.status} /></div>
                  {result.stages.transportation?.total_cost != null && (
                    <p className="mt-1 text-xs text-muted">cost: {formatNumber(result.stages.transportation.total_cost, 2)}</p>
                  )}
                </div>
              </div>
            )}
            {result.stages?.transportation?.flows && Object.keys(result.stages.transportation.flows).length > 0 && (
              <table className="mt-4 w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="py-2 pr-4 font-medium">Lane</th>
                    <th className="py-2 pr-4 font-medium">Flow</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.stages.transportation.flows).map(([lane, flow]) => (
                    <tr key={lane} className="border-b border-border last:border-0">
                      <td className="py-1.5 pr-4">{lane}</td>
                      <td className="py-1.5 pr-4">{formatNumber(flow, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  )
}

export function OptimizationPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Optimization</h1>
        <p className="mt-1 text-sm text-muted">
          Run the full network pipeline on the database, or experiment with hand-written networks in the sandbox tabs.
        </p>
      </div>
      <Tabs
        defaultKey="network"
        tabs={[
          { key: 'network', label: 'Network run', content: <NetworkRunner /> },
          { key: 'gsm', label: 'Sandbox: GSM', content: <GsmRunner /> },
          { key: 'forecast', label: 'Sandbox: Forecast', content: <ForecastRunner /> },
          { key: 'pipeline', label: 'Sandbox: Pipeline', content: <PipelineRunner /> },
        ]}
      />
    </div>
  )
}
