import { useState, type SubmitEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, KeyRound, UserPlus } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { ROLE_DESCRIPTION, ROLE_LABEL, useAuth } from '@/lib/auth-context'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { FormRow, Input, Select } from '@/components/ui/Field'
import { ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { formatDateTime } from '@/lib/utils'
import type { Role, UserOut } from '@/lib/types'

const ROLES: Role[] = ['admin', 'planner', 'viewer']
const MIN_LENGTH = 8

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback
}

function generatePassword(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
  const bytes = new Uint32Array(12)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => chars[b % chars.length]).join('')
}

function AddUserForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('viewer')
  const [password, setPassword] = useState(generatePassword)
  const [created, setCreated] = useState<{ email: string; password: string } | null>(null)

  const create = useMutation({
    mutationFn: () => api.createUser({ name, email, role, password }),
    onSuccess: (user) => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setCreated({ email: user.email, password })
      setName('')
      setEmail('')
      setRole('viewer')
      setPassword(generatePassword())
    },
  })

  function onSubmit(e: SubmitEvent) {
    e.preventDefault()
    setCreated(null)
    create.mutate()
  }

  return (
    <Card>
      <CardHeader
        title="Add a user"
        description="Share the email and temporary password with them; they can change it under Account."
        action={<Button variant="ghost" size="sm" onClick={onDone}>Close</Button>}
      />
      <CardBody>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          {create.isError && <ErrorNotice title="User not created" message={errorMessage(create.error, 'Please try again.')} />}
          {created && (
            <div className="flex items-start gap-2 rounded-lg bg-ok-50 px-4 py-3 text-sm text-ok-700">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                Created <strong>{created.email}</strong> with temporary password{' '}
                <code className="rounded bg-white px-1.5 py-0.5 font-mono text-xs text-slate-900">{created.password}</code>. Copy it now —
                it won’t be shown again.
              </p>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <FormRow label="Full name">
              <Input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
            </FormRow>
            <FormRow label="Email">
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </FormRow>
            <FormRow label="Role" hint={ROLE_DESCRIPTION[role]}>
              <Select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>{ROLE_LABEL[r]}</option>
                ))}
              </Select>
            </FormRow>
            <FormRow label="Temporary password" hint={`At least ${MIN_LENGTH} characters.`}>
              <div className="flex gap-2">
                <Input value={password} onChange={(e) => setPassword(e.target.value)} className="font-mono" />
                <Button type="button" variant="secondary" onClick={() => setPassword(generatePassword())}>
                  New
                </Button>
              </div>
            </FormRow>
          </div>
          <div>
            <Button type="submit" loading={create.isPending} disabled={!name.trim() || !email.trim() || password.length < MIN_LENGTH}>
              <UserPlus className="h-4 w-4" /> Add user
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  )
}

function ResetPassword({ user }: { user: UserOut }) {
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const reset = useMutation({ mutationFn: () => api.resetUserPassword(user.id, password) })

  if (!open) {
    return (
      <Button variant="ghost" size="sm" onClick={() => { setPassword(generatePassword()); reset.reset(); setOpen(true) }}>
        <KeyRound className="h-3.5 w-3.5" /> Reset password
      </Button>
    )
  }
  if (reset.isSuccess) {
    return (
      <div className="flex flex-wrap items-center gap-2 text-xs text-ok-700">
        New password: <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-900">{password}</code>
        <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>Done</Button>
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <Input value={password} onChange={(e) => setPassword(e.target.value)} className="h-8 w-40 font-mono text-xs" aria-label="New password" />
        <Button size="sm" onClick={() => reset.mutate()} loading={reset.isPending} disabled={password.length < MIN_LENGTH}>Set</Button>
        <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
      {reset.isError && <p className="text-xs text-danger-700">{errorMessage(reset.error, 'Reset failed')}</p>}
    </div>
  )
}

function UserRow({ user, isSelf }: { user: UserOut; isSelf: boolean }) {
  const queryClient = useQueryClient()
  const update = useMutation({
    mutationFn: (payload: { role?: Role; is_active?: boolean }) => api.updateUser(user.id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })

  return (
    <tr className="border-b border-border align-top last:border-0">
      <td className="px-5 py-3">
        <p className="font-medium text-slate-900">
          {user.name} {isSelf && <span className="text-xs font-normal text-muted">(you)</span>}
        </p>
        <p className="break-all text-xs text-muted">{user.email}</p>
        {update.isError && <p className="mt-1 text-xs text-danger-700">{errorMessage(update.error, 'Update failed')}</p>}
      </td>
      <td className="px-5 py-3">
        <Select
          className="h-8 w-32 py-1"
          value={user.role}
          disabled={isSelf || update.isPending}
          title={isSelf ? 'You can’t change your own role' : undefined}
          onChange={(e) => update.mutate({ role: e.target.value as Role })}
          aria-label={`Role for ${user.name}`}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>{ROLE_LABEL[r]}</option>
          ))}
        </Select>
      </td>
      <td className="px-5 py-3">
        {user.is_active ? <Badge tone="ok">Active</Badge> : <Badge tone="neutral">Deactivated</Badge>}
      </td>
      <td className="whitespace-nowrap px-5 py-3 text-muted">{formatDateTime(user.last_login_at ?? null)}</td>
      <td className="px-5 py-3">
        <div className="flex flex-wrap items-start justify-end gap-1">
          <ResetPassword user={user} />
          {!isSelf && (
            <Button
              variant="ghost"
              size="sm"
              loading={update.isPending}
              onClick={() => update.mutate({ is_active: !user.is_active })}
            >
              {user.is_active ? 'Deactivate' : 'Reactivate'}
            </Button>
          )}
        </div>
      </td>
    </tr>
  )
}

export function UsersPage() {
  const { user: me } = useAuth()
  const [adding, setAdding] = useState(false)
  const users = useQuery({ queryKey: ['users'], queryFn: api.listUsers })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Admin"
        title="Users"
        description="Who can sign in, and what they can do."
        actions={!adding && <Button size="sm" onClick={() => setAdding(true)}><UserPlus className="h-4 w-4" /> Add user</Button>}
      />

      <div className="grid gap-3 sm:grid-cols-3">
        {ROLES.map((r) => (
          <div key={r} className="card px-4 py-3">
            <Badge tone={r === 'admin' ? 'brand' : r === 'planner' ? 'ok' : 'neutral'}>{ROLE_LABEL[r]}</Badge>
            <p className="mt-1.5 text-xs text-muted">{ROLE_DESCRIPTION[r]}</p>
          </div>
        ))}
      </div>

      {adding && <AddUserForm onDone={() => setAdding(false)} />}

      <Card>
        <CardHeader title="Accounts" description={users.data ? `${users.data.length} user${users.data.length === 1 ? '' : 's'}` : undefined} />
        <CardBody className="overflow-x-auto p-0">
          {users.isLoading && <Spinner />}
          {users.isError && <div className="p-5"><ErrorNotice message={errorMessage(users.error, 'Failed to load users')} /></div>}
          {users.data && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-5 py-2.5 font-medium">User</th>
                    <th className="px-5 py-2.5 font-medium">Role</th>
                    <th className="px-5 py-2.5 font-medium">Status</th>
                    <th className="px-5 py-2.5 font-medium">Last sign-in</th>
                    <th className="px-5 py-2.5 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {users.data.map((u) => (
                    <UserRow key={u.id} user={u} isSelf={u.id === me?.id} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
