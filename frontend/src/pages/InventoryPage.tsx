import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, CardHeader } from '@/components/ui/Card'
import { ErrorNotice, EmptyState, Spinner } from '@/components/ui/Feedback'
import { Button } from '@/components/ui/Button'
import { formatNumber } from '@/lib/utils'
import type { LocationOut, ProductOut } from '@/lib/types'

const PAGE_SIZE = 10

function Pager({ skip, setSkip, count }: { skip: number; setSkip: (n: number) => void; count: number }) {
  return (
    <div className="flex items-center justify-between border-t border-border px-5 py-3 text-xs text-muted">
      <span>
        Showing {count === 0 ? 0 : skip + 1}–{skip + count}
      </span>
      <div className="flex gap-1.5">
        <Button variant="secondary" size="sm" onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))} disabled={skip === 0}>
          <ChevronLeft className="h-3.5 w-3.5" /> Prev
        </Button>
        <Button variant="secondary" size="sm" onClick={() => setSkip(skip + PAGE_SIZE)} disabled={count < PAGE_SIZE}>
          Next <ChevronRight className="h-3.5 w-3.5" />
        </Button>
      </div>
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
      {data && data.length === 0 && (
        <EmptyState title="No locations found" description="Seed the database to populate the network." />
      )}
      {data && data.length > 0 && (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-5 py-2.5 font-medium">Name</th>
                <th className="px-5 py-2.5 font-medium">Type</th>
                <th className="px-5 py-2.5 font-medium">Region</th>
                <th className="px-5 py-2.5 font-medium">ID</th>
              </tr>
            </thead>
            <tbody>
              {data.map((loc: LocationOut) => (
                <tr key={loc.id} className="border-b border-border last:border-0 hover:bg-slate-50">
                  <td className="px-5 py-2.5 font-medium text-slate-900">{loc.name}</td>
                  <td className="px-5 py-2.5 text-muted">{loc.type}</td>
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
      {data && data.length === 0 && (
        <EmptyState title="No products found" description="Seed the database to populate the catalog." />
      )}
      {data && data.length > 0 && (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-5 py-2.5 font-medium">Name</th>
                <th className="px-5 py-2.5 font-medium">SKU</th>
                <th className="px-5 py-2.5 font-medium">Category</th>
                <th className="px-5 py-2.5 font-medium">Unit cost</th>
                <th className="px-5 py-2.5 font-medium">ID</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p: ProductOut) => (
                <tr key={p.id} className="border-b border-border last:border-0 hover:bg-slate-50">
                  <td className="px-5 py-2.5 font-medium text-slate-900">{p.name}</td>
                  <td className="px-5 py-2.5 text-muted">{p.sku ?? '—'}</td>
                  <td className="px-5 py-2.5 text-muted">{p.category ?? '—'}</td>
                  <td className="px-5 py-2.5 text-muted">{p.unit_cost != null ? `$${formatNumber(p.unit_cost, 2)}` : '—'}</td>
                  <td className="px-5 py-2.5 font-mono text-xs text-slate-400">{p.id}</td>
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
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Inventory</h1>
        <p className="mt-1 text-sm text-muted">Locations and products currently known to the platform.</p>
      </div>
      <LocationsTable />
      <ProductsTable />
    </div>
  )
}
