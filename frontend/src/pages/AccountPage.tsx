import { useState, type SubmitEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { CheckCircle2 } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { ROLE_DESCRIPTION, ROLE_LABEL, useAuth } from '@/lib/auth-context'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { FormRow, Input } from '@/components/ui/Field'
import { ErrorNotice } from '@/components/ui/Feedback'
import { formatDateTime } from '@/lib/utils'

const MIN_LENGTH = 8

export function AccountPage() {
  const { user } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  const change = useMutation({
    mutationFn: () => api.changePassword(current, next),
    onSuccess: () => {
      setCurrent('')
      setNext('')
      setConfirm('')
    },
  })

  function onSubmit(e: SubmitEvent) {
    e.preventDefault()
    setLocalError(null)
    change.reset()
    if (next.length < MIN_LENGTH) return setLocalError(`Use at least ${MIN_LENGTH} characters.`)
    if (next !== confirm) return setLocalError('The new passwords don’t match.')
    change.mutate()
  }

  if (!user) return null

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <PageHeader eyebrow="Account" title="Your account" description="Your profile and sign-in details." />

      <Card>
        <CardHeader title="Profile" />
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs font-medium text-muted">Name</p>
            <p className="mt-0.5 text-sm text-slate-900">{user.name}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted">Email</p>
            <p className="mt-0.5 break-all text-sm text-slate-900">{user.email}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted">Role</p>
            <div className="mt-1 flex flex-col items-start gap-1">
              <Badge tone="brand">{ROLE_LABEL[user.role]}</Badge>
              <p className="text-xs text-muted">{ROLE_DESCRIPTION[user.role]}</p>
            </div>
          </div>
          <div>
            <p className="text-xs font-medium text-muted">Last sign-in</p>
            <p className="mt-0.5 text-sm text-slate-900">{formatDateTime(user.last_login_at ?? null)}</p>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Change password" description={`At least ${MIN_LENGTH} characters.`} />
        <CardBody>
          <form onSubmit={onSubmit} className="flex max-w-sm flex-col gap-4">
            {(localError || change.isError) && (
              <ErrorNotice
                title="Password not changed"
                message={localError ?? (change.error instanceof ApiError ? change.error.message : 'Please try again.')}
              />
            )}
            {change.isSuccess && (
              <p className="flex items-center gap-2 rounded-lg bg-ok-50 px-3 py-2 text-sm text-ok-700">
                <CheckCircle2 className="h-4 w-4" /> Password changed.
              </p>
            )}
            <FormRow label="Current password">
              <Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
            </FormRow>
            <FormRow label="New password">
              <Input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
            </FormRow>
            <FormRow label="Confirm new password">
              <Input type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </FormRow>
            <div>
              <Button type="submit" loading={change.isPending} disabled={!current || !next || !confirm}>
                Change password
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  )
}
