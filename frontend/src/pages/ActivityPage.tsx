import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Field'
import { EmptyState, ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { formatDateTime } from '@/lib/utils'
import type { AuditEventOut } from '@/lib/types'

const PAGE_SIZE = 50

const ACTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All activity' },
  { value: 'pipeline.', label: 'Pipeline runs' },
  { value: 'policy.', label: 'Policy edits' },
  { value: 'alert.', label: 'Alerts resolved' },
  { value: 'data.', label: 'Data imports & loads' },
  { value: 'user.', label: 'User changes' },
]

const ACTION_LABEL: Record<string, string> = {
  'pipeline.run': 'Started a pipeline run',
  'policy.update': 'Edited a policy',
  'alert.resolve': 'Resolved an alert',
  'data.import': 'Imported a file',
  'data.demo_load': 'Loaded demo data',
  'demand.ingest': 'Ingested demand via API',
  'user.create': 'Added a user',
  'user.update': 'Changed a user',
  'user.reset_password': 'Reset a user’s password',
  'user.change_password': 'Changed own password',
}

function describe(e: AuditEventOut): string {
  const d = e.details ?? {}
  switch (e.action) {
    case 'policy.update': {
      const { location, sku, ...fields } = d as Record<string, unknown>
      const changes = Object.entries(fields).map(([k, v]) => `${k.replace(/_/g, ' ')} → ${v}`).join(', ')
      return `${location} / ${sku}: ${changes}`
    }
    case 'data.import':
      return String(d.filename ?? '')
    case 'pipeline.run':
      return `${String(d.run_type ?? '')} run ${e.entity_id?.slice(0, 8) ?? ''}`
    case 'alert.resolve':
      return String(d.message ?? '')
    case 'user.create':
      return `${d.email} as ${d.role}`
    case 'user.update': {
      const { email, ...rest } = d as Record<string, unknown>
      return `${email}: ${Object.entries(rest).map(([k, v]) => `${k.replace(/_/g, ' ')} → ${v}`).join(', ')}`
    }
    case 'user.reset_password':
      return String(d.email ?? '')
    case 'data.demo_load':
      return d.reset ? 'replaced all planning data' : 'added to existing data'
    default:
      return ''
  }
}

export function ActivityPage() {
  const [action, setAction] = useState('')
  const [skip, setSkip] = useState(0)
  const events = useQuery({
    queryKey: ['audit', action, skip],
    queryFn: () => api.listAudit({ action: action || undefined, skip, limit: PAGE_SIZE + 1 }),
    placeholderData: (prev) => prev,
  })
  const rows = events.data?.slice(0, PAGE_SIZE)
  const hasNext = (events.data?.length ?? 0) > PAGE_SIZE

  return (
    <div className="flex flex-col gap-6">
      <PageHeader eyebrow="Admin" title="Activity log" description="Who changed what, and when. Entries can’t be edited or deleted." />
      <Card>
        <CardHeader
          title="Activity"
          action={
            <Select className="w-52" value={action} onChange={(e) => { setAction(e.target.value); setSkip(0) }} aria-label="Filter activity">
              {ACTIONS.map((a) => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </Select>
          }
        />
        <CardBody className="overflow-x-auto p-0">
          {events.isLoading && <Spinner />}
          {events.isError && (
            <div className="p-5">
              <ErrorNotice message={events.error instanceof ApiError ? events.error.message : 'Failed to load activity'} />
            </div>
          )}
          {rows && rows.length === 0 && <EmptyState title="No activity yet" />}
          {rows && rows.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-5 py-2.5 font-medium">When</th>
                    <th className="px-5 py-2.5 font-medium">Who</th>
                    <th className="px-5 py-2.5 font-medium">What</th>
                    <th className="px-5 py-2.5 font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((e) => (
                    <tr key={e.id} className="border-b border-border last:border-0">
                      <td className="whitespace-nowrap px-5 py-2.5 text-muted">{formatDateTime(e.created_at)}</td>
                      <td className="px-5 py-2.5 text-slate-900">
                        {e.user_email === 'system' ? <Badge tone="neutral">Scheduled job</Badge> : e.user_email}
                      </td>
                      <td className="whitespace-nowrap px-5 py-2.5 font-medium text-slate-900">{ACTION_LABEL[e.action] ?? e.action}</td>
                      <td className="px-5 py-2.5 text-xs text-slate-600">{describe(e)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {(skip > 0 || hasNext) && (
            <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
              <Button variant="secondary" size="sm" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}>Newer</Button>
              <Button variant="secondary" size="sm" disabled={!hasNext} onClick={() => setSkip(skip + PAGE_SIZE)}>Older</Button>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
