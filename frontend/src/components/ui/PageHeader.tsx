import type { ReactNode } from 'react'

export function PageHeader({
  eyebrow,
  title,
  description,
  badges,
  actions,
}: {
  eyebrow: string
  title: string
  description?: string
  badges?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">{eyebrow}</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-900">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {badges && <div className="flex flex-wrap items-center gap-2">{badges}</div>}
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}
