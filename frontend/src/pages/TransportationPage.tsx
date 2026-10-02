import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatTile, StatTileGrid } from '@/components/ui/StatTile'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Select } from '@/components/ui/Field'
import { EmptyState, ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { formatNumber } from '@/lib/utils'

export function TransportationPage() {
  const [productId, setProductId] = useState<string>('')

  const products = useQuery({ queryKey: ['products', 0, 100], queryFn: () => api.listProducts(0, 100) })
  const plan = useQuery({
    queryKey: ['transportation-plan', productId],
    queryFn: () => api.getTransportationPlan(productId ? { product_id: productId } : {}),
  })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Flow plan"
        title="Transportation"
        description="Lane-level replenishment quantities produced by the optimization run, with capacity utilization and cost."
      />

      {plan.isLoading && <Spinner />}
      {plan.isError && (
        <ErrorNotice message={plan.error instanceof ApiError ? plan.error.message : 'Failed to load transportation plan'} />
      )}

      {plan.data && plan.data.status === 'NO_DEMAND_DATA' && (
        <EmptyState
          title="No demand data to plan against"
          description={plan.data.message ?? 'No recent Store-level demand history found.'}
        />
      )}
      {plan.data && plan.data.status === 'NO_EDGES' && (
        <EmptyState title="No lanes configured" description="Add lanes between locations to compute a transportation plan." />
      )}
      {plan.data && plan.data.status === 'INFEASIBLE' && (
        <ErrorNotice title="No feasible flow" message={plan.data.message ?? 'The lane network cannot satisfy current demand.'} />
      )}

      {plan.data && plan.data.status === 'OPTIMAL' && (
        <>
          <StatTileGrid>
            <StatTile label="Planned units" value={formatNumber(plan.data.planned_units, 0)} unit="u" />
            <StatTile label="Transport cost" value={`$${formatNumber(plan.data.total_cost / 1000, 1)}`} unit="K" />
            <StatTile
              label="Capacity utilization"
              value={plan.data.capacity_utilization != null ? formatNumber(plan.data.capacity_utilization * 100, 1) : '—'}
              unit="%"
              tone={
                plan.data.capacity_utilization != null && plan.data.capacity_utilization > 0.9
                  ? 'warn'
                  : 'default'
              }
            />
            <StatTile label="Active lanes" value={String(plan.data.active_lanes)} />
          </StatTileGrid>

          <Card>
            <CardHeader
              title="Lane flows"
              description="Source → target movements per SKU"
              action={
                <Select className="w-40" value={productId} onChange={(e) => setProductId(e.target.value)}>
                  <option value="">All SKUs</option>
                  {products.data?.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.sku ?? p.name}
                    </option>
                  ))}
                </Select>
              }
            />
            <CardBody className="p-0">
              {plan.data.lane_flows.length === 0 && (
                <EmptyState title="No flows" description="The plan produced no positive flows for this selection." />
              )}
              {plan.data.lane_flows.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                        <th className="px-4 py-2.5 font-medium">Source</th>
                        <th className="px-4 py-2.5 font-medium">Target</th>
                        <th className="px-4 py-2.5 font-medium">SKU</th>
                        <th className="px-4 py-2.5 font-medium">Quantity</th>
                        <th className="px-4 py-2.5 font-medium">Capacity</th>
                        <th className="px-4 py-2.5 font-medium">Utilization</th>
                        <th className="px-4 py-2.5 font-medium">Transit</th>
                        <th className="px-4 py-2.5 font-medium">Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plan.data.lane_flows.map((flow, idx) => (
                        <tr key={`${flow.lane_id}-${flow.product_id}-${idx}`} className="border-b border-border last:border-0 hover:bg-slate-50">
                          <td className="px-4 py-2 whitespace-nowrap">
                            {flow.source_name} <Badge tone="neutral">{flow.source_type}</Badge>
                          </td>
                          <td className="px-4 py-2 whitespace-nowrap">
                            {flow.target_name} <Badge tone="neutral">{flow.target_type}</Badge>
                          </td>
                          <td className="px-4 py-2 text-muted">{flow.sku ?? flow.product_name}</td>
                          <td className="px-4 py-2">{formatNumber(flow.quantity, 0)}</td>
                          <td className="px-4 py-2 text-muted">{flow.capacity != null ? formatNumber(flow.capacity, 0) : '—'}</td>
                          <td className="px-4 py-2">
                            {flow.utilization != null ? (
                              <div className="flex items-center gap-2">
                                <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                                  <div
                                    className="h-full rounded-full bg-brand-600"
                                    style={{ width: `${Math.min(100, flow.utilization * 100)}%` }}
                                  />
                                </div>
                                <span className="text-xs text-muted">{formatNumber(flow.utilization * 100, 0)}%</span>
                              </div>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>
                          <td className="px-4 py-2 text-muted">{flow.transit_time ?? '—'}d</td>
                          <td className="px-4 py-2 text-muted">${formatNumber(flow.cost, 0)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}
