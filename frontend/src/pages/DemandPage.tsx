import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Upload } from 'lucide-react'
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, ApiError } from '@/lib/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatTile, StatTileGrid } from '@/components/ui/StatTile'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input, Select } from '@/components/ui/Field'
import { cn, formatDate, formatNumber } from '@/lib/utils'
import { EmptyState, ErrorNotice, Spinner } from '@/components/ui/Feedback'
import type { DemandRecord } from '@/lib/types'

const HISTORY_WINDOWS = [56, 90, 120] as const
const HORIZONS = [7, 14, 28] as const

const PATTERN_HELP: Record<string, string> = {
  smooth: 'Regular demand — exponential smoothing family',
  erratic: 'Regular but volatile — exponential smoothing family',
  intermittent: 'Many zero days — Croston / SBA / TSB',
  lumpy: 'Many zero days and volatile sizes — Croston / SBA / TSB',
}

function Segmented<T extends number>({ options, value, onChange, suffix }: { options: readonly T[]; value: T; onChange: (v: T) => void; suffix: string }) {
  return (
    <div className="flex gap-1 rounded-lg border border-border p-1">
      {options.map((o) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
            value === o ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100',
          )}
        >
          {o}{suffix}
        </button>
      ))}
    </div>
  )
}

function formatParams(params: Record<string, number>): string {
  const entries = Object.entries(params)
  return entries.length ? entries.map(([k, v]) => `${k}=${v}`).join(', ') : '—'
}

function DemandAnalytics() {
  const stores = useQuery({ queryKey: ['locations', 'Store'], queryFn: () => api.listLocations(0, 1000, 'Store') })
  const products = useQuery({ queryKey: ['products', 0, 1000], queryFn: () => api.listProducts(0, 1000) })
  const [locationId, setLocationId] = useState('')
  const [productId, setProductId] = useState('')
  const [historyDays, setHistoryDays] = useState<(typeof HISTORY_WINDOWS)[number]>(90)
  const [horizon, setHorizon] = useState<(typeof HORIZONS)[number]>(14)

  const forecast = useQuery({
    queryKey: ['demand-forecast', locationId, productId, historyDays, horizon],
    queryFn: () => api.getDemandForecast({ location_id: locationId, product_id: productId, history_days: historyDays, horizon }),
    enabled: !!locationId && !!productId,
  })

  const chartData = useMemo(() => {
    const f = forecast.data
    if (!f) return []
    const backtest = new Map(f.backtest.map((b) => [b.date, b.forecast]))
    const rows: { date: string; actual?: number; backtest?: number; forecast?: number; band?: [number, number] }[] =
      f.history.map((h) => ({ date: h.date, actual: h.quantity, backtest: backtest.get(h.date) }))
    for (const p of f.forecast) rows.push({ date: p.date, forecast: p.forecast, band: [p.lower, p.upper] })
    return rows
  }, [forecast.data])

  const f = forecast.data

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="Signal"
        title="Demand & forecast"
        description="Each series is classified by its demand pattern, every suitable model is backtested on the most recent weeks, and the most accurate one (lowest MASE) produces the forecast."
        badges={
          f && (
            <>
              <Badge tone="brand">{f.method.toUpperCase()}</Badge>
              <Badge tone="neutral">{f.pattern.toUpperCase()}</Badge>
            </>
          )
        }
      />
      <Card>
        <CardBody>
          <div className="flex flex-wrap items-center gap-3">
            <Select className="w-64" value={locationId} onChange={(e) => setLocationId(e.target.value)}>
              <option value="">Select store…</option>
              {stores.data?.map((l) => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </Select>
            <Select className="w-64" value={productId} onChange={(e) => setProductId(e.target.value)}>
              <option value="">Select SKU…</option>
              {products.data?.map((p) => (
                <option key={p.id} value={p.id}>{p.sku ? `${p.sku} — ${p.name}` : p.name}</option>
              ))}
            </Select>
            <div className="flex items-center gap-2 text-xs text-muted">
              History <Segmented options={HISTORY_WINDOWS} value={historyDays} onChange={setHistoryDays} suffix="d" />
            </div>
            <div className="flex items-center gap-2 text-xs text-muted">
              Horizon <Segmented options={HORIZONS} value={horizon} onChange={setHorizon} suffix="d" />
            </div>
          </div>

          <div className="mt-5">
            {!locationId || !productId ? (
              <EmptyState title="Choose a store and SKU" description="The forecast, its accuracy and a comparison of every candidate model will appear here." />
            ) : forecast.isLoading ? (
              <Spinner />
            ) : forecast.isError ? (
              <ErrorNotice message={forecast.error instanceof ApiError ? forecast.error.message : 'Failed to load forecast'} />
            ) : f ? (
              <>
                <StatTileGrid>
                  <StatTile
                    label="Demand pattern"
                    value={f.pattern.charAt(0).toUpperCase() + f.pattern.slice(1)}
                    caption={f.adi != null && f.cv2 != null ? `ADI ${formatNumber(f.adi, 2)} · CV² ${formatNumber(f.cv2, 2)}` : PATTERN_HELP[f.pattern]}
                  />
                  <StatTile label="Selected model" value={f.method} caption={formatParams(f.params)} />
                  <StatTile
                    label="MASE (holdout)"
                    value={f.metrics?.mase != null ? formatNumber(f.metrics.mase, 2) : '—'}
                    caption="< 1 beats a seasonal-naive forecast"
                    tone={f.metrics?.mase != null && f.metrics.mase > 1 ? 'warn' : 'ok'}
                  />
                  <StatTile
                    label="MAPE (holdout)"
                    value={f.metrics?.mape != null ? formatNumber(f.metrics.mape, 1) : '—'}
                    unit="%"
                    caption={f.metrics?.bias != null ? `bias ${f.metrics.bias >= 0 ? '+' : ''}${formatNumber(f.metrics.bias, 2)} u/day` : undefined}
                  />
                  <StatTile
                    label="Forecast demand"
                    value={formatNumber(f.demand_mean, 1)}
                    unit="u/day"
                    caption={`error σ ${formatNumber(f.demand_std, 2)} u — drives safety stock`}
                  />
                </StatTileGrid>

                <div className="mt-5 h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={formatDate} minTickGap={24} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip labelFormatter={(d) => formatDate(String(d))} formatter={(v) => (Array.isArray(v) ? v.map((x) => formatNumber(Number(x), 1)).join(' – ') : formatNumber(Number(v), 1))} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Area dataKey="band" name="95% interval" stroke="none" fill="#6366f1" fillOpacity={0.12} />
                      <Line type="monotone" dataKey="actual" name="Actual" stroke="#0f172a" strokeWidth={1.5} dot={false} />
                      <Line type="monotone" dataKey="backtest" name="Backtest" stroke="#d97706" strokeWidth={2} strokeDasharray="4 3" dot={false} />
                      <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#4f46e5" strokeWidth={2} dot={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </>
            ) : null}
          </div>
        </CardBody>
      </Card>

      {f && f.leaderboard.length > 0 && (
        <Card>
          <CardHeader title="Model comparison" description="Every candidate is fitted on the training window and scored on the holdout window; lowest MASE wins" />
          <CardBody className="overflow-x-auto p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-5 py-2.5 font-medium">Model</th>
                    <th className="px-5 py-2.5 font-medium">Parameters</th>
                    <th className="px-5 py-2.5 text-right font-medium">MASE</th>
                    <th className="px-5 py-2.5 text-right font-medium">MAE</th>
                    <th className="px-5 py-2.5 text-right font-medium">RMSE</th>
                    <th className="px-5 py-2.5 text-right font-medium">MAPE</th>
                    <th className="px-5 py-2.5 text-right font-medium">Bias</th>
                  </tr>
                </thead>
                <tbody>
                  {f.leaderboard.map((m) => (
                    <tr key={m.method} className={cn('border-b border-border last:border-0', m.selected && 'bg-brand-50/50')}>
                      <td className="px-5 py-2 font-medium text-slate-900">
                        {m.method} {m.selected && <Badge tone="brand">selected</Badge>}
                      </td>
                      <td className="px-5 py-2 font-mono text-xs text-muted">{formatParams(m.params)}</td>
                      <td className="px-5 py-2 text-right">{formatNumber(m.mase, 3)}</td>
                      <td className="px-5 py-2 text-right text-muted">{formatNumber(m.mae, 2)}</td>
                      <td className="px-5 py-2 text-right text-muted">{formatNumber(m.rmse, 2)}</td>
                      <td className="px-5 py-2 text-right text-muted">{m.mape != null ? `${formatNumber(m.mape, 1)}%` : '—'}</td>
                      <td className="px-5 py-2 text-right text-muted">{formatNumber(m.bias, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}

interface DraftRow {
  location_id: string
  product_id: string
  date: string
  quantity: string
}

function emptyRow(): DraftRow {
  return { location_id: '', product_id: '', date: '', quantity: '' }
}

function IngestForm() {
  const locations = useQuery({ queryKey: ['locations', 'Store'], queryFn: () => api.listLocations(0, 1000, 'Store') })
  const products = useQuery({ queryKey: ['products', 0, 1000], queryFn: () => api.listProducts(0, 1000) })
  const queryClient = useQueryClient()
  const [rows, setRows] = useState<DraftRow[]>([emptyRow()])

  const mutation = useMutation({
    mutationFn: (records: DemandRecord[]) => api.ingestDemand(records),
    onSuccess: () => {
      setRows([emptyRow()])
      queryClient.invalidateQueries({ queryKey: ['demand-forecast'] })
    },
  })

  const updateRow = (idx: number, patch: Partial<DraftRow>) =>
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)))

  const canSubmit = rows.every((r) => r.location_id && r.product_id && r.date && r.quantity !== '')

  return (
    <Card>
      <CardHeader title="Ingest demand" description="Bulk upsert historical demand records" />
      <CardBody>
        <div className="flex flex-col gap-2.5">
          {rows.map((row, idx) => (
            <div key={idx} className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_140px_100px_36px]">
              <Select value={row.location_id} onChange={(e) => updateRow(idx, { location_id: e.target.value })}>
                <option value="">Location…</option>
                {locations.data?.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </Select>
              <Select value={row.product_id} onChange={(e) => updateRow(idx, { product_id: e.target.value })}>
                <option value="">Product…</option>
                {products.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.sku ? `${p.sku} — ${p.name}` : p.name}
                  </option>
                ))}
              </Select>
              <Input type="date" value={row.date} onChange={(e) => updateRow(idx, { date: e.target.value })} />
              <Input
                type="number"
                min={0}
                step="any"
                placeholder="Qty"
                value={row.quantity}
                onChange={(e) => updateRow(idx, { quantity: e.target.value })}
              />
              <button
                type="button"
                aria-label="Remove row"
                className="flex items-center justify-center rounded-lg text-slate-400 hover:bg-danger-50 hover:text-danger-600"
                onClick={() => setRows((prev) => (prev.length > 1 ? prev.filter((_, i) => i !== idx) : prev))}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>

        <div className="mt-3 flex items-center justify-between">
          <Button variant="secondary" size="sm" onClick={() => setRows((prev) => [...prev, emptyRow()])}>
            <Plus className="h-3.5 w-3.5" /> Add row
          </Button>
          <Button
            size="sm"
            loading={mutation.isPending}
            disabled={!canSubmit}
            onClick={() =>
              mutation.mutate(
                rows.map((r) => ({
                  location_id: r.location_id,
                  product_id: r.product_id,
                  date: r.date,
                  quantity: Number(r.quantity),
                })),
              )
            }
          >
            <Upload className="h-3.5 w-3.5" /> Ingest {rows.length} record{rows.length === 1 ? '' : 's'}
          </Button>
        </div>

        {mutation.isError && (
          <div className="mt-3">
            <ErrorNotice message={mutation.error instanceof ApiError ? mutation.error.message : 'Failed to ingest demand'} />
          </div>
        )}
        {mutation.isSuccess && (
          <div className="mt-3 text-sm">
            <p className="text-ok-700">
              {mutation.data.inserted_count} inserted · {mutation.data.updated_count} updated · {mutation.data.ignored_count} ignored
            </p>
            {mutation.data.errors.length > 0 && <p className="mt-1 text-danger-700">{mutation.data.errors.join('; ')}</p>}
          </div>
        )}
      </CardBody>
    </Card>
  )
}

export function DemandPage() {
  return (
    <div className="flex flex-col gap-6">
      <DemandAnalytics />
      <IngestForm />
    </div>
  )
}
