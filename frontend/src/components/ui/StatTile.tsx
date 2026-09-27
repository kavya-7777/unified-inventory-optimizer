import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

type Tone = 'default' | 'ok' | 'warn' | 'danger'

const valueTone: Record<Tone, string> = {
  default: 'text-slate-900',
  ok: 'text-ok-600',
  warn: 'text-warn-600',
  danger: 'text-danger-600',
}

export function StatTile({
  label,
  value,
  unit,
  caption,
  tone = 'default',
}: {
  label: string
  value: string
  unit?: string
  caption?: string
  tone?: Tone
}) {
  return (
    <div className="card px-5 py-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className={cn('mt-1.5 text-2xl font-bold', valueTone[tone])}>
        {value}
        {unit && <span className="ml-1 text-sm font-medium text-muted">{unit}</span>}
      </p>
      {caption && <p className="mt-0.5 text-xs text-muted">{caption}</p>}
    </div>
  )
}

export function StatTileGrid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">{children}</div>
}
