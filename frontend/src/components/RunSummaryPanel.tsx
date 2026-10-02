import { StatTile, StatTileGrid } from '@/components/ui/StatTile'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { formatCurrency, formatDate, formatNumber } from '@/lib/utils'
import type { RunSummary } from '@/lib/types'

function Breakdown({ title, counts }: { title: string; counts: Record<string, number> }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1])
  return (
    <div className="rounded-lg border border-border p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {entries.map(([name, n]) => (
          <Badge key={name} tone="neutral">
            {name} · {n}
          </Badge>
        ))}
      </div>
    </div>
  )
}

export function RunSummaryPanel({ summary }: { summary: RunSummary }) {
  const t = summary.transportation
  return (
    <div className="flex flex-col gap-4">
      <StatTileGrid>
        <StatTile
          label="SKUs optimized"
          value={`${summary.products_optimized}/${summary.products}`}
          caption={`${summary.nodes_optimized} node-SKU targets`}
          tone={summary.failures.length ? 'warn' : 'default'}
        />
        <StatTile
          label="Series forecast"
          value={String(summary.series_forecast)}
          caption={summary.median_mase != null ? `median MASE ${formatNumber(summary.median_mase, 2)}` : undefined}
        />
        <StatTile
          label="Safety stock value"
          value={formatCurrency(summary.safety_stock_value, true)}
          caption={`${formatNumber(summary.total_safety_stock_units)} units`}
        />
        <StatTile
          label="Holding cost"
          value={formatCurrency(summary.holding_cost_per_day)}
          unit="/day"
          caption="for the safety stock"
        />
        <StatTile
          label="Stockout risks"
          value={String(summary.stockout_alerts)}
          tone={summary.stockout_alerts ? 'danger' : 'ok'}
          caption="on hand below safety stock"
        />
      </StatTileGrid>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <Breakdown title="Demand patterns" counts={summary.demand_patterns} />
        <Breakdown title="Selected forecast models" counts={summary.forecast_methods} />
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Transportation plan</p>
          <div className="mt-2 flex items-center gap-2">
            <StatusBadge status={t.status} />
            {t.total_cost != null && <span className="text-sm text-slate-900">{formatCurrency(t.total_cost)}/day</span>}
          </div>
          {t.planned_units != null && (
            <p className="mt-1 text-xs text-muted">
              {formatNumber(t.planned_units)} units/day over {t.active_lanes} lanes
              {t.capacity_utilization != null && ` · ${formatNumber(t.capacity_utilization * 100, 0)}% of capacity`}
            </p>
          )}
        </div>
      </div>

      <p className="text-xs text-muted">
        {summary.history_days} days of history up to {formatDate(summary.history_end)}, {summary.horizon}-day forecast horizon.
        {summary.fallback_products.length > 0 && ` Heuristic fallback used for ${summary.fallback_products.length} SKU(s).`}
      </p>
      {summary.failures.length > 0 && (
        <div className="rounded-lg border border-warn-600/30 bg-warn-50 p-3 text-xs text-warn-700">
          {summary.failures.map((f) => (
            <p key={f.product_id}>
              {f.product_id}: {f.errors.join('; ')}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
