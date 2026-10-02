import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { api } from '@/lib/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatTile, StatTileGrid } from '@/components/ui/StatTile'
import { Badge } from '@/components/ui/Badge'
import { ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { formatNumber } from '@/lib/utils'
import type { LocationOut } from '@/lib/types'

/** Short display code, e.g. "Reno West DC" (DC) -> "DC-RENO". Cosmetic only — the
 * real primary key is a UUID, not fit for display. */
function shortCode(location: LocationOut): string {
  const prefix = { Supplier: 'SUP', DC: 'DC', Store: 'STR' }[location.type] ?? location.type.slice(0, 3).toUpperCase()
  const letters = location.name.replace(/[^A-Za-z0-9]/g, '').toUpperCase().slice(0, 5)
  return `${prefix}-${letters}`
}

const GROUPS: { type: string; title: string; description: string }[] = [
  { type: 'Supplier', title: 'Suppliers', description: 'External supply, unconstrained upstream' },
  { type: 'DC', title: 'Distribution centers', description: 'Pooling echelon, decoupling stock' },
  { type: 'Store', title: 'Stores', description: 'Customer-facing, demand origin' },
]

export function NetworkPage() {
  const locations = useQuery({ queryKey: ['locations', 0, 1000], queryFn: () => api.listLocations(0, 1000) })
  const lanes = useQuery({ queryKey: ['lanes'], queryFn: api.listLanes })
  const policies = useQuery({ queryKey: ['policies', 'all'], queryFn: () => api.listPolicies({ limit: 1000 }) })
  const alerts = useQuery({
    queryKey: ['alerts', 'unresolved', 1000],
    queryFn: () => api.listAlerts({ resolved: false, limit: 1000 }),
  })

  const isLoading = locations.isLoading || lanes.isLoading || policies.isLoading || alerts.isLoading
  const firstError = locations.error ?? lanes.error ?? policies.error ?? alerts.error

  const skuCountByLocation = useMemo(() => {
    const map = new Map<string, number>()
    for (const p of policies.data ?? []) map.set(p.location_id, (map.get(p.location_id) ?? 0) + 1)
    return map
  }, [policies.data])

  const atRiskLocationIds = useMemo(() => {
    const set = new Set<string>()
    for (const a of alerts.data ?? []) if (a.location_id) set.add(a.location_id)
    return set
  }, [alerts.data])

  const stats = useMemo(() => {
    const laneList = lanes.data ?? []
    const avgTransit = laneList.length ? laneList.reduce((sum, l) => sum + l.transit_time, 0) / laneList.length : 0
    const avgCost = laneList.length ? laneList.reduce((sum, l) => sum + l.cost_per_unit, 0) / laneList.length : 0
    const stockingNodes = skuCountByLocation.size
    return { avgTransit, avgCost, stockingNodes }
  }, [lanes.data, skuCountByLocation])

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Topology"
        title="Supply network"
        description="Three-echelon network. Lane transit times feed the guaranteed-service model as processing times; service-time decisions propagate downstream."
        badges={
          <>
            <Badge tone="neutral">{(locations.data ?? []).length} NODES</Badge>
            <Badge tone="brand">{(lanes.data ?? []).length} LANES</Badge>
          </>
        }
      />

      {isLoading && <Spinner />}
      {firstError && <ErrorNotice message={(firstError as Error).message} />}

      {!isLoading && !firstError && (
        <>
          <StatTileGrid>
            <StatTile label="Avg inbound transit" value={formatNumber(stats.avgTransit, 1)} unit="days" />
            <StatTile label="Avg lane cost" value={`$${formatNumber(stats.avgCost, 2)}`} unit="/unit" />
            <StatTile label="Stocking nodes" value={String(stats.stockingNodes)} />
          </StatTileGrid>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {GROUPS.map((group) => {
              const groupLocations = (locations.data ?? []).filter((l) => l.type === group.type)
              return (
                <div key={group.type} className="card">
                  <div className="border-b border-border px-4 py-3">
                    <h3 className="text-sm font-semibold text-slate-900">{group.title}</h3>
                    <p className="text-xs text-muted">{group.description}</p>
                  </div>
                  <div className="flex flex-col divide-y divide-border">
                    {groupLocations.length === 0 && (
                      <p className="px-4 py-6 text-center text-xs text-muted">No {group.title.toLowerCase()} yet.</p>
                    )}
                    {groupLocations.map((loc) => {
                      const skuCount = skuCountByLocation.get(loc.id) ?? 0
                      const atRisk = atRiskLocationIds.has(loc.id)
                      return (
                        <div key={loc.id} className="flex items-center justify-between px-4 py-2.5">
                          <div>
                            <p className="text-sm font-medium text-slate-900">{loc.name}</p>
                            <p className="font-mono text-xs text-slate-400">{shortCode(loc)}</p>
                          </div>
                          <div className="flex items-center gap-2 text-right">
                            {atRisk && (
                              <span className="inline-flex items-center gap-1 text-xs font-medium text-danger-600">
                                <AlertTriangle className="h-3.5 w-3.5" /> at risk
                              </span>
                            )}
                            <div>
                              {loc.region && <p className="text-xs text-muted">{loc.region}</p>}
                              {skuCount > 0 && <p className="text-xs text-muted">{skuCount} SKUs</p>}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
