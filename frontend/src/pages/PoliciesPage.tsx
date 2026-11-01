import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatTile, StatTileGrid } from '@/components/ui/StatTile'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input, Select } from '@/components/ui/Field'
import { EmptyState, ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { formatNumber } from '@/lib/utils'
import { useAuth } from '@/lib/auth-context'
import type { PolicyOut, PolicyUpdate } from '@/lib/types'

type EditableField = keyof PolicyUpdate
const EDITABLE_FIELDS: { key: EditableField; label: string; step?: string }[] = [
  { key: 'service_level', label: 'Service level %', step: '0.1' },
  { key: 'min_s_out', label: 'Min S_out' },
  { key: 'max_s_out', label: 'Max S_out' },
  { key: 'holding_cost', label: 'Holding cost', step: '0.01' },
  { key: 'ordering_cost', label: 'Ordering cost', step: '0.01' },
  { key: 'review_period', label: 'Review period' },
  { key: 'processing_time', label: 'Processing days' },
]

const PAGE_SIZE = 50

export function PoliciesPage() {
  const { can } = useAuth()
  const canEdit = can('planner')
  const [search, setSearch] = useState('')
  const [locationId, setLocationId] = useState('')
  const [skip, setSkip] = useState(0)
  const [edits, setEdits] = useState<Record<string, PolicyUpdate>>({})
  const queryClient = useQueryClient()

  const locations = useQuery({ queryKey: ['locations', 0, 1000], queryFn: () => api.listLocations(0, 1000) })
  const summary = useQuery({ queryKey: ['dashboard-summary'], queryFn: api.getDashboardSummary })
  // Ask for one extra row to know whether a next page exists.
  const page = useQuery({
    queryKey: ['policies', search, locationId, skip],
    queryFn: () =>
      api.listPolicies({ q: search || undefined, location_id: locationId || undefined, skip, limit: PAGE_SIZE + 1 }),
    placeholderData: (prev) => prev,
  })
  const data = page.data?.slice(0, PAGE_SIZE)
  const hasNext = (page.data?.length ?? 0) > PAGE_SIZE
  const { isLoading, isError, error } = page

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
        description={
          canEdit
            ? 'Service levels and cost parameters per node-SKU. Changes here feed the next optimization run.'
            : 'Service levels and cost parameters per node-SKU. Read-only: planners and admins can edit these.'
        }
        actions={
          canEdit && <>
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
        <StatTile label="Policies" value={summary.data ? String(summary.data.total_policies) : '—'} caption="location × SKU pairs" />
        <StatTile
          label="Avg service level"
          value={summary.data?.avg_service_level != null ? formatNumber(summary.data.avg_service_level * 100, 1) : '—'}
          unit="%"
          caption="across all policies"
        />
        {canEdit && (
          <StatTile label="Unsaved edits" value={String(unsavedCount)} tone={unsavedCount > 0 ? 'warn' : 'default'} caption="kept while you page through" />
        )}
      </StatTileGrid>

      <Card>
        <CardHeader
          title="Policy grid"
          description={canEdit ? 'Inline editable' : 'Read-only'}
          action={
            <div className="flex flex-wrap gap-2">
              <Select
                className="w-60"
                value={locationId}
                onChange={(e) => {
                  setLocationId(e.target.value)
                  setSkip(0)
                }}
              >
                <option value="">All locations</option>
                {locations.data?.map((l) => (
                  <option key={l.id} value={l.id}>{l.name}</option>
                ))}
              </Select>
              <Input
                className="w-56"
                placeholder="Search location, product or SKU"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setSkip(0)
                }}
              />
            </div>
          }
        />
        <CardBody className="overflow-x-auto p-0">
          {isLoading && <Spinner />}
          {isError && <div className="p-5"><ErrorNotice message={(error as Error).message} /></div>}
          {data && data.length === 0 && <EmptyState title="No policies found" />}
          {data && data.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-2.5 font-medium">Node</th>
                    <th className="px-4 py-2.5 font-medium">Product</th>
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
                        <td className="whitespace-nowrap px-4 py-2">
                          <p className="text-slate-900">{policy.product_name}</p>
                          <p className="font-mono text-xs text-muted">{policy.product_sku}</p>
                        </td>
                        {EDITABLE_FIELDS.map((f) => (
                          <td key={f.key} className="px-2 py-1.5">
                            {!canEdit ? (
                              <span className="block w-24 px-3 py-1 tabular-nums text-slate-700">
                                {f.key === 'service_level'
                                  ? formatNumber(policy.service_level * 100, 1)
                                  : formatNumber(policy[f.key], f.step ? 2 : 0)}
                              </span>
                            ) : (
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
                            )}
                          </td>
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          {data && data.length > 0 && (
            <div className="flex items-center justify-between border-t border-border px-5 py-3 text-xs text-muted">
              <span>Showing {skip + 1}–{skip + data.length}</span>
              <div className="flex gap-1.5">
                <Button variant="secondary" size="sm" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}>
                  <ChevronLeft className="h-3.5 w-3.5" /> Prev
                </Button>
                <Button variant="secondary" size="sm" disabled={!hasNext} onClick={() => setSkip(skip + PAGE_SIZE)}>
                  Next <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
