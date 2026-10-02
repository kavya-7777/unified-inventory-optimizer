import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { FormRow, Input, Textarea } from '@/components/ui/Field'
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
      <CardHeader title="Demand forecast" description="Runs SES / Holt / Croston-SBA depending on demand pattern — no DB persistence" />
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
                  <th className="py-2 pr-4 font-medium">Forecast</th>
                </tr>
              </thead>
              <tbody>
                {result.forecasts.map((f) => (
                  <tr key={f.id} className="border-b border-border last:border-0">
                    <td className="py-1.5 pr-4 font-medium text-slate-900">{f.id}</td>
                    <td className="py-1.5 pr-4">{f.pattern}</td>
                    <td className="py-1.5 pr-4">{f.method}</td>
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
          Run the GSM solver, demand forecasting, or the full daily pipeline on demand.
        </p>
      </div>
      <Tabs
        defaultKey="gsm"
        tabs={[
          { key: 'gsm', label: 'GSM Optimization', content: <GsmRunner /> },
          { key: 'forecast', label: 'Forecast', content: <ForecastRunner /> },
          { key: 'pipeline', label: 'Full Pipeline', content: <PipelineRunner /> },
        ]}
      />
    </div>
  )
}
