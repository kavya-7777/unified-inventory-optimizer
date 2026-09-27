import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Upload } from 'lucide-react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, ApiError } from '@/lib/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatTile, StatTileGrid } from '@/components/ui/StatTile'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input, Select } from '@/components/ui/Field'
import { cn, formatNumber } from '@/lib/utils'
import { EmptyState, ErrorNotice, Spinner } from '@/components/ui/Feedback'
import type { DemandRecord } from '@/lib/types'

function useLocationsAndProducts() {
  const locations = useQuery({ queryKey: ['locations', 0, 100], queryFn: () => api.listLocations(0, 100) })
  const products = useQuery({ queryKey: ['products', 0, 100], queryFn: () => api.listProducts(0, 100) })
  return { locations, products }
}

const PERIODS = [7, 14, 28, 56] as const

function mean(values: number[]): number {
  return values.length ? values.reduce((s, v) => s + v, 0) / values.length : 0
}

function stdDev(values: number[]): number {
  if (values.length < 2) return 0
  const m = mean(values)
  return Math.sqrt(values.reduce((s, v) => s + (v - m) ** 2, 0) / values.length)
}

function DemandAnalytics() {
  const { locations, products } = useLocationsAndProducts()
  const [locationId, setLocationId] = useState('')
  const [productId, setProductId] = useState('')
  const [periodDays, setPeriodDays] = useState<(typeof PERIODS)[number]>(28)

  const endDate = new Date()
  const startDate = new Date(endDate.getTime() - periodDays * 86_400_000)
  const iso = (d: Date) => d.toISOString().slice(0, 10)

  const history = useQuery({
    queryKey: ['demand-history', locationId, productId, periodDays],
    queryFn: () => api.getDemandHistory({ location_id: locationId, product_id: productId, start_date: iso(startDate), end_date: iso(endDate) }),
    enabled: !!locationId && !!productId,
  })

  const quantities = useMemo(() => (history.data ?? []).map((r) => r.quantity), [history.data])
  const stats = useMemo(() => {
    const m = mean(quantities)
    const sd = stdDev(quantities)
    const zeroDays = quantities.filter((q) => q === 0).length
    return {
      mean: m,
      stdDev: sd,
      cv: m > 0 ? sd / m : null,
      zeroDemandPct: quantities.length ? (zeroDays / quantities.length) * 100 : null,
    }
  }, [quantities])

  // Classification badge (pattern/method) over the full selected window.
  const classification = useQuery({
    queryKey: ['forecast-classify', locationId, productId, periodDays, quantities.length],
    queryFn: () => api.runForecast({ items: [{ id: 'selection', history: quantities }], horizon: 1 }),
    enabled: quantities.length >= 4,
  })

  // Backtest for MAPE/bias: train on the first ~70%, forecast the rest, compare to actual.
  const splitIdx = Math.floor(quantities.length * 0.7)
  const train = quantities.slice(0, splitIdx)
  const test = quantities.slice(splitIdx)
  const backtest = useQuery({
    queryKey: ['forecast-backtest', locationId, productId, periodDays, quantities.length],
    queryFn: () => api.runForecast({ items: [{ id: 'selection', history: train }], horizon: test.length }),
    enabled: quantities.length >= 8 && test.length > 0,
  })

  const accuracy = useMemo(() => {
    const forecast = backtest.data?.forecasts[0]?.forecast
    if (!forecast || forecast.length !== test.length) return { mape: null as number | null, bias: null as number | null }
    const pairs = test.map((actual, i) => ({ actual, forecast: forecast[i] })).filter((p) => p.actual > 0)
    if (pairs.length === 0) return { mape: null, bias: null }
    const mape = mean(pairs.map((p) => Math.abs(p.actual - p.forecast) / p.actual)) * 100
    const bias = mean(pairs.map((p) => (p.forecast - p.actual) / p.actual)) * 100
    return { mape, bias }
  }, [backtest.data, test])

  const chartData = useMemo(() => {
    const rows = (history.data ?? []).map((r, i) => ({ date: r.date, actual: r.quantity, forecast: undefined as number | undefined, isTest: i >= splitIdx }))
    const forecastValues = backtest.data?.forecasts[0]?.forecast
    if (forecastValues) {
      rows.forEach((row, i) => {
        if (i >= splitIdx) row.forecast = forecastValues[i - splitIdx]
      })
    }
    return rows
  }, [history.data, backtest.data, splitIdx])

  const pattern = classification.data?.forecasts[0]?.pattern
  const method = classification.data?.forecasts[0]?.method

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="Signal"
        title="Demand & forecast"
        description="Demand history drives pattern classification, which selects the forecast method: Holt-DES for smooth series, SES for erratic, Croston-SBA for intermittent and lumpy."
        badges={
          <>
            {method && <Badge tone="brand">{method.toUpperCase()}</Badge>}
            {pattern && pattern !== 'INSUFFICIENT_DATA' && <Badge tone="neutral">{pattern.toUpperCase()}</Badge>}
          </>
        }
      />
      <Card>
      <CardBody>
        <div className="flex flex-wrap items-center gap-3">
          <Select className="w-56" value={locationId} onChange={(e) => setLocationId(e.target.value)}>
            <option value="">Select location…</option>
            {locations.data?.map((l) => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </Select>
          <Select className="w-56" value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">Select SKU…</option>
            {products.data?.map((p) => (
              <option key={p.id} value={p.id}>{p.sku ? `${p.sku} — ${p.name}` : p.name}</option>
            ))}
          </Select>
          <div className="flex gap-1 rounded-lg border border-border p-1">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriodDays(p)}
                className={cn(
                  'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                  periodDays === p ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100',
                )}
              >
                {p}d
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5">
          {!locationId || !productId ? (
            <EmptyState title="Choose a location and SKU" description="Stats and a history/forecast chart will appear here." />
          ) : history.isLoading ? (
            <Spinner />
          ) : history.isError ? (
            <ErrorNotice message={history.error instanceof ApiError ? history.error.message : 'Failed to load demand history'} />
          ) : history.data && history.data.length === 0 ? (
            <EmptyState title="No demand history" description="No records for this location/SKU/period." />
          ) : (
            <>
              <StatTileGrid>
                <StatTile label={`Mean (${periodDays}d)`} value={formatNumber(stats.mean, 1)} unit="u/day" />
                <StatTile label={`Std dev (${periodDays}d)`} value={formatNumber(stats.stdDev, 1)} unit="u" />
                <StatTile label="CV" value={stats.cv != null ? formatNumber(stats.cv, 2) : '—'} />
                <StatTile label="Zero-demand days" value={stats.zeroDemandPct != null ? formatNumber(stats.zeroDemandPct, 0) : '—'} unit="%" />
                <StatTile
                  label="MAPE"
                  value={accuracy.mape != null ? formatNumber(accuracy.mape, 1) : '—'}
                  unit="%"
                  caption={accuracy.bias != null ? `bias ${accuracy.bias >= 0 ? '+' : ''}${formatNumber(accuracy.bias, 1)}%` : undefined}
                  tone={accuracy.mape != null && accuracy.mape > 50 ? 'warn' : 'default'}
                />
              </StatTileGrid>

              <div className="mt-5 h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line type="monotone" dataKey="actual" name="Actual" stroke="#4f46e5" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="forecast" name="Forecast (backtest)" stroke="#d97706" strokeWidth={2} strokeDasharray="4 3" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      </CardBody>
      </Card>
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
  const { locations, products } = useLocationsAndProducts()
  const queryClient = useQueryClient()
  const [rows, setRows] = useState<DraftRow[]>([emptyRow()])

  const mutation = useMutation({
    mutationFn: (records: DemandRecord[]) => api.ingestDemand(records),
    onSuccess: () => {
      setRows([emptyRow()])
      queryClient.invalidateQueries({ queryKey: ['demand-history'] })
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
                    {p.name}
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
          <p className="mt-3 text-sm text-ok-700">
            Ingested {mutation.data.inserted_count} record{mutation.data.inserted_count === 1 ? '' : 's'}.
          </p>
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
