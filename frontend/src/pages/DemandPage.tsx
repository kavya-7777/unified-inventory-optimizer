import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Upload } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, ApiError } from '@/lib/api'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { FormRow, Input, Select } from '@/components/ui/Field'
import { EmptyState, ErrorNotice, Spinner } from '@/components/ui/Feedback'
import type { DemandRecord } from '@/lib/types'

function useLocationsAndProducts() {
  const locations = useQuery({ queryKey: ['locations', 0, 100], queryFn: () => api.listLocations(0, 100) })
  const products = useQuery({ queryKey: ['products', 0, 100], queryFn: () => api.listProducts(0, 100) })
  return { locations, products }
}

function HistoryExplorer() {
  const { locations, products } = useLocationsAndProducts()
  const [locationId, setLocationId] = useState('')
  const [productId, setProductId] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [submitted, setSubmitted] = useState<{ location_id: string; product_id: string; start_date?: string; end_date?: string } | null>(null)

  const history = useQuery({
    queryKey: ['demand-history', submitted],
    queryFn: () => api.getDemandHistory(submitted!),
    enabled: !!submitted,
  })

  const chartData = useMemo(
    () => (history.data ?? []).map((r) => ({ date: r.date, quantity: r.quantity })),
    [history.data],
  )

  return (
    <Card>
      <CardHeader title="Demand history" description="Query historical demand for a location/product pair" />
      <CardBody>
        <form
          className="grid grid-cols-1 gap-3 sm:grid-cols-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (!locationId || !productId) return
            setSubmitted({
              location_id: locationId,
              product_id: productId,
              start_date: startDate || undefined,
              end_date: endDate || undefined,
            })
          }}
        >
          <FormRow label="Location">
            <Select value={locationId} onChange={(e) => setLocationId(e.target.value)} required>
              <option value="">Select location…</option>
              {locations.data?.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </Select>
          </FormRow>
          <FormRow label="Product">
            <Select value={productId} onChange={(e) => setProductId(e.target.value)} required>
              <option value="">Select product…</option>
              {products.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </FormRow>
          <FormRow label="Start date" hint="optional">
            <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </FormRow>
          <FormRow label="End date" hint="optional">
            <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </FormRow>
          <div className="sm:col-span-4">
            <Button type="submit" loading={history.isFetching}>
              Fetch history
            </Button>
          </div>
        </form>

        <div className="mt-5">
          {!submitted && (
            <EmptyState title="Choose a location and product" description="Results will appear as a chart and table below." />
          )}
          {history.isLoading && submitted && <Spinner />}
          {history.isError && <ErrorNotice message={(history.error as Error).message} />}
          {history.data && history.data.length === 0 && (
            <EmptyState title="No demand history" description="No records for this location/product/date range." />
          )}
          {history.data && history.data.length > 0 && (
            <>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="quantity" stroke="#4f46e5" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-4 max-h-64 overflow-y-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-white">
                    <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                      <th className="px-4 py-2 font-medium">Date</th>
                      <th className="px-4 py-2 font-medium">Quantity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.data.map((r) => (
                      <tr key={r.id} className="border-b border-border last:border-0">
                        <td className="px-4 py-1.5">{r.date}</td>
                        <td className="px-4 py-1.5">{r.quantity}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </CardBody>
    </Card>
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
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Demand</h1>
        <p className="mt-1 text-sm text-muted">Explore historical demand and ingest new records.</p>
      </div>
      <HistoryExplorer />
      <IngestForm />
    </div>
  )
}
