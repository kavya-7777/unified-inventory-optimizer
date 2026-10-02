import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, CardHeader } from '@/components/ui/Card'
import { ErrorNotice, EmptyState, Spinner } from '@/components/ui/Feedback'
import { Button } from '@/components/ui/Button'
import { Input, Select } from '@/components/ui/Field'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatTile, StatTileGrid } from '@/components/ui/StatTile'
import { Tabs } from '@/components/ui/Tabs'
import { formatCurrency, formatDate, formatNumber, humanize } from '@/lib/utils'
import type { LocationOut, PositionStatus, ProductOut } from '@/lib/types'

const PAGE_SIZE = 25

const STATUS_HELP: Record<PositionStatus, string> = {
  STOCKOUT_RISK: 'On hand below safety stock',
  REORDER: 'Inventory position at or below reorder point',
  EXCESS: 'On hand above reorder point + order quantity',
  HEALTHY: 'Within policy',
  NO_PLAN: 'No optimization result yet',
}

function Pager({ skip, setSkip, count, total }: { skip: number; setSkip: (n: number) => void; count: number; total?: number }) {
  return (
    <div className="flex items-center justify-between border-t border-border px-5 py-3 text-xs text-muted">
      <span>
        Showing {count === 0 ? 0 : skip + 1}–{skip + count}
        {total != null && ` of ${total}`}
      </span>
      <div className="flex gap-1.5">
        <Button variant="secondary" size="sm" onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))} disabled={skip === 0}>
          <ChevronLeft className="h-3.5 w-3.5" /> Prev
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setSkip(skip + PAGE_SIZE)}
          disabled={total != null ? skip + count >= total : count < PAGE_SIZE}
        >
          Next <ChevronRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}

function PositionsTable() {
  const [skip, setSkip] = useState(0)
  const [locationType, setLocationType] = useState('')
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['inventory-positions', locationType, status, search, skip],
    queryFn: () =>
      api.getInventoryPositions({
        location_type: locationType || undefined,
        status: status || undefined,
        q: search || undefined,
        skip,
        limit: PAGE_SIZE,
      }),
    placeholderData: (prev) => prev,
  })

  const reset = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v)
    setSkip(0)
  }

  return (
    <div className="flex flex-col gap-4">
      {data && (
        <StatTileGrid>
          <StatTile label="Stockout risk" value={String(data.counts.STOCKOUT_RISK)} tone={data.counts.STOCKOUT_RISK ? 'danger' : 'default'} caption={STATUS_HELP.STOCKOUT_RISK} />
          <StatTile label="Reorder now" value={String(data.counts.REORDER)} tone={data.counts.REORDER ? 'warn' : 'default'} caption={STATUS_HELP.REORDER} />
          <StatTile label="Excess" value={String(data.counts.EXCESS)} caption={STATUS_HELP.EXCESS} />
          <StatTile label="Healthy" value={String(data.counts.HEALTHY)} tone="ok" caption={STATUS_HELP.HEALTHY} />
          <StatTile label="No plan" value={String(data.counts.NO_PLAN)} caption="Run the network pipeline" />
        </StatTileGrid>
      )}

      <Card>
        <CardHeader
          title="Inventory positions"
          description="Latest stock per location and SKU against the most recent optimized targets"
          action={
            <div className="flex flex-wrap gap-2">
              <Input className="w-48" placeholder="Search store, SKU, category" value={search} onChange={(e) => reset(setSearch)(e.target.value)} />
              <Select className="w-32" value={locationType} onChange={(e) => reset(setLocationType)(e.target.value)}>
                <option value="">All nodes</option>
                <option value="Store">Stores</option>
                <option value="DC">DCs</option>
              </Select>
              <Select className="w-40" value={status} onChange={(e) => reset(setStatus)(e.target.value)}>
                <option value="">All statuses</option>
                {(Object.keys(STATUS_HELP) as PositionStatus[]).map((s) => (
                  <option key={s} value={s}>{humanize(s)}</option>
                ))}
              </Select>
            </div>
          }
        />
        {isLoading && <Spinner />}
        {isError && <div className="p-5"><ErrorNotice message={(error as Error).message} /></div>}
        {data && data.items.length === 0 && (
          <EmptyState title="No inventory positions" description="Seed the database or adjust the filters." />
        )}
        {data && data.items.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-2.5 font-medium">Location</th>
                    <th className="px-4 py-2.5 font-medium">Product</th>
                    <th className="px-4 py-2.5 text-right font-medium">On hand</th>
                    <th className="px-4 py-2.5 text-right font-medium">On order + transit</th>
                    <th className="px-4 py-2.5 text-right font-medium">Safety stock</th>
                    <th className="px-4 py-2.5 text-right font-medium">Reorder point</th>
                    <th className="px-4 py-2.5 text-right font-medium">Days of cover</th>
                    <th className="px-4 py-2.5 text-right font-medium">Suggested order</th>
                    <th className="px-4 py-2.5 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((p) => (
                    <tr key={`${p.location_id}-${p.product_id}`} className="border-b border-border last:border-0 hover:bg-slate-50">
                      <td className="whitespace-nowrap px-4 py-2">
                        <p className="font-medium text-slate-900">{p.location_name}</p>
                        <p className="text-xs text-muted">{p.location_type} · {p.region ?? '—'}</p>
                      </td>
                      <td className="px-4 py-2">
                        <p className="text-slate-900">{p.product_name}</p>
                        <p className="text-xs text-muted">{p.sku} · {p.category}</p>
                      </td>
                      <td className="px-4 py-2 text-right font-medium">{formatNumber(p.on_hand)}</td>
                      <td className="px-4 py-2 text-right text-muted">{formatNumber(p.on_order + p.in_transit)}</td>
                      <td className="px-4 py-2 text-right">{formatNumber(p.safety_stock, 1)}</td>
                      <td className="px-4 py-2 text-right">{formatNumber(p.reorder_point, 1)}</td>
                      <td className="px-4 py-2 text-right text-muted">{p.days_of_cover != null ? `${formatNumber(p.days_of_cover, 1)} d` : '—'}</td>
                      <td className="px-4 py-2 text-right">{p.recommended_order > 0 ? formatNumber(p.recommended_order) : '—'}</td>
                      <td className="px-4 py-2" title={STATUS_HELP[p.status]}>
                        <StatusBadge status={p.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager skip={skip} setSkip={setSkip} count={data.items.length} total={data.total} />
          </>
        )}
      </Card>
      {data && data.items[0] && (
        <p className="text-xs text-muted">Snapshot date: {formatDate(data.items[0].snapshot_date)}</p>
      )}
    </div>
  )
}

function LocationsTable() {
  const [skip, setSkip] = useState(0)
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['locations', skip, PAGE_SIZE],
    queryFn: () => api.listLocations(skip, PAGE_SIZE),
    placeholderData: (prev) => prev,
  })

  return (
    <Card>
      <CardHeader title="Locations" description="Suppliers, distribution centers and stores" />
      {isLoading && <Spinner />}
      {isError && <div className="p-5"><ErrorNotice message={(error as Error).message} /></div>}
      {data && data.length === 0 && <EmptyState title="No locations found" description="Seed the database to populate the network." />}
      {data && data.length > 0 && (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-5 py-2.5 font-medium">Name</th>
                <th className="px-5 py-2.5 font-medium">Type</th>
                <th className="px-5 py-2.5 font-medium">Region</th>
                <th className="px-5 py-2.5 font-medium">Code</th>
              </tr>
            </thead>
            <tbody>
              {data.map((loc: LocationOut) => (
                <tr key={loc.id} className="border-b border-border last:border-0 hover:bg-slate-50">
                  <td className="px-5 py-2.5 font-medium text-slate-900">{loc.name}</td>
                  <td className="px-5 py-2.5"><Badge tone="neutral">{loc.type}</Badge></td>
                  <td className="px-5 py-2.5 text-muted">{loc.region ?? '—'}</td>
                  <td className="px-5 py-2.5 font-mono text-xs text-slate-400">{loc.id}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager skip={skip} setSkip={setSkip} count={data.length} />
        </>
      )}
    </Card>
  )
}

function ProductsTable() {
  const [skip, setSkip] = useState(0)
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['products', skip, PAGE_SIZE],
    queryFn: () => api.listProducts(skip, PAGE_SIZE),
    placeholderData: (prev) => prev,
  })

  return (
    <Card>
      <CardHeader title="Products" description="SKUs tracked across the network" />
      {isLoading && <Spinner />}
      {isError && <div className="p-5"><ErrorNotice message={(error as Error).message} /></div>}
      {data && data.length === 0 && <EmptyState title="No products found" description="Seed the database to populate the catalog." />}
      {data && data.length > 0 && (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-5 py-2.5 font-medium">Name</th>
                <th className="px-5 py-2.5 font-medium">SKU</th>
                <th className="px-5 py-2.5 font-medium">Category</th>
                <th className="px-5 py-2.5 text-right font-medium">Unit cost</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p: ProductOut) => (
                <tr key={p.id} className="border-b border-border last:border-0 hover:bg-slate-50">
                  <td className="px-5 py-2.5 font-medium text-slate-900">{p.name}</td>
                  <td className="px-5 py-2.5 font-mono text-xs text-muted">{p.sku ?? '—'}</td>
                  <td className="px-5 py-2.5 text-muted">{p.category ?? '—'}</td>
                  <td className="px-5 py-2.5 text-right">{formatCurrency(p.unit_cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager skip={skip} setSkip={setSkip} count={data.length} />
        </>
      )}
    </Card>
  )
}

export function InventoryPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Stock"
        title="Inventory"
        description="Where stock stands today versus the safety stock and reorder points from the latest optimization run."
      />
      <Tabs
        defaultKey="positions"
        tabs={[
          { key: 'positions', label: 'Positions', content: <PositionsTable /> },
          { key: 'locations', label: 'Locations', content: <LocationsTable /> },
          { key: 'products', label: 'Products', content: <ProductsTable /> },
        ]}
      />
    </div>
  )
}
