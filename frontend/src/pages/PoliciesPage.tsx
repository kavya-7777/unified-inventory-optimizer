import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatTile, StatTileGrid } from '@/components/ui/StatTile'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Field'
import { EmptyState, ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { formatNumber } from '@/lib/utils'
import type { PolicyOut, PolicyUpdate } from '@/lib/types'

type EditableField = keyof PolicyUpdate
const EDITABLE_FIELDS: { key: EditableField; label: string; step?: string }[] = [
  { key: 'service_level', label: 'Service level %', step: '0.1' },
  { key: 'min_s_out', label: 'Min S_out' },
  { key: 'max_s_out', label: 'Max S_out' },
  { key: 'holding_cost', label: 'Holding cost', step: '0.01' },
  { key: 'ordering_cost', label: 'Ordering cost', step: '0.01' },
  { key: 'review_period', label: 'Review period' },
]

export function PoliciesPage() {
  const [search, setSearch] = useState('')
  const [edits, setEdits] = useState<Record<string, PolicyUpdate>>({})
  const queryClient = useQueryClient()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['policies', search],
    queryFn: () => api.listPolicies({ q: search || undefined, limit: 500 }),
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      const entries = Object.entries(edits)
      return Promise.all(entries.map(([id, fields]) => api.updatePolicy(id, fields)))
    },
    onSuccess: () => {
      setEdits({})
      queryClient.invalidateQueries({ queryKey: ['policies'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
  })

  const stats = useMemo(() => {
    const rows = data ?? []
    const avgServiceLevel = rows.length ? rows.reduce((s, r) => s + r.service_level, 0) / rows.length : null
    const avgReviewPeriod = rows.length ? rows.reduce((s, r) => s + r.review_period, 0) / rows.length : null
    return { total: rows.length, avgServiceLevel, avgReviewPeriod }
  }, [data])

  const unsavedCount = Object.keys(edits).length

  function fieldValue(policy: PolicyOut, field: EditableField): number {
    return edits[policy.id]?.[field] ?? policy[field]
  }

  function setField(policy: PolicyOut, field: EditableField, raw: string) {
    const value = field === 'service_level' ? Number(raw) / 100 : Number(raw)
    if (Number.isNaN(value)) return
    setEdits((prev) => ({ ...prev, [policy.id]: { ...prev[policy.id], [field]: value } }))
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Configuration"
        title="Policies"
        description="Service levels and cost parameters per node-SKU. Changes here feed the next optimization run."
        actions={
          <>
            <Button variant="secondary" size="sm" disabled={unsavedCount === 0} onClick={() => setEdits({})}>
              Discard
            </Button>
            <Button
              size="sm"
              disabled={unsavedCount === 0}
              loading={saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
            >
              Save
            </Button>
          </>
        }
      />

      {saveMutation.isError && (
        <ErrorNotice message={saveMutation.error instanceof ApiError ? saveMutation.error.message : 'Failed to save policies'} />
      )}

      <StatTileGrid>
        <StatTile label="Policies" value={String(stats.total)} />
        <StatTile
          label="Avg service level"
          value={stats.avgServiceLevel != null ? formatNumber(stats.avgServiceLevel * 100, 1) : '—'}
          unit="%"
        />
        <StatTile label="Avg review period" value={stats.avgReviewPeriod != null ? formatNumber(stats.avgReviewPeriod, 1) : '—'} unit="days" />
        <StatTile label="Unsaved edits" value={String(unsavedCount)} tone={unsavedCount > 0 ? 'warn' : 'default'} />
      </StatTileGrid>

      <Card>
        <CardHeader
          title="Policy grid"
          description="Inline editable"
          action={
            <Input
              className="w-56"
              placeholder="Filter node or SKU"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          }
        />
        <CardBody className="p-0">
          {isLoading && <Spinner />}
          {isError && <div className="p-5"><ErrorNotice message={(error as Error).message} /></div>}
          {data && data.length === 0 && <EmptyState title="No policies found" />}
          {data && data.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-2.5 font-medium">Node</th>
                    <th className="px-4 py-2.5 font-medium">SKU</th>
                    {EDITABLE_FIELDS.map((f) => (
                      <th key={f.key} className="px-4 py-2.5 font-medium">{f.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.map((policy) => {
                    const dirty = !!edits[policy.id]
                    return (
                      <tr key={policy.id} className={dirty ? 'bg-warn-50/40' : 'hover:bg-slate-50'}>
                        <td className="whitespace-nowrap px-4 py-2">
                          {policy.location_name} <Badge tone="neutral">{policy.location_type}</Badge>
                        </td>
                        <td className="whitespace-nowrap px-4 py-2 text-muted">{policy.product_sku ?? policy.product_name}</td>
                        {EDITABLE_FIELDS.map((f) => (
                          <td key={f.key} className="px-2 py-1.5">
                            <Input
                              type="number"
                              step={f.step}
                              className="w-24 py-1"
                              value={
                                f.key === 'service_level'
                                  ? Math.round(fieldValue(policy, f.key) * 1000) / 10
                                  : fieldValue(policy, f.key)
                              }
                              onChange={(e) => setField(policy, f.key, e.target.value)}
                            />
                          </td>
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
