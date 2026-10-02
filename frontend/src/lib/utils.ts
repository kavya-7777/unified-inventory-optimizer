import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge Tailwind class names, resolving conflicts (last one wins). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Format a number with thousands separators; falls back to '—' for null/undefined/NaN. */
export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/** The backend stores naive UTC timestamps; mark them as UTC so they render in local time. */
function parseTimestamp(value: string): Date {
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/i.test(value)
  return new Date(hasZone || !value.includes('T') ? value : `${value}Z`)
}

export const CURRENCY = 'INR'

/** Currency with Indian digit grouping; `compact` gives e.g. ₹1.1 Cr / ₹4.5 L. */
export function formatCurrency(value: number | null | undefined, compact = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: CURRENCY,
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 2 : value < 100 ? 2 : 0,
  }).format(value)
}

/** "2026-10-02" → "2 Oct" */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(`${value.slice(0, 10)}T00:00:00`)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

/** "STOCKOUT_RISK" → "Stockout risk" */
export function humanize(value: string | null | undefined): string {
  if (!value) return '—'
  const text = value.replace(/_/g, ' ').toLowerCase()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Format an ISO datetime string as a short, readable local date-time. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = parseTimestamp(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Format a duration in seconds as e.g. "1.24s" or "340ms". */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return '—'
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  return `${seconds.toFixed(2)}s`
}

export type BadgeTone = 'ok' | 'warn' | 'danger' | 'neutral' | 'brand'

/** Maps common backend status strings to a visual badge tone. */
export function toneForStatus(status: string | null | undefined): BadgeTone {
  const s = (status ?? '').toUpperCase()
  if (['OPTIMAL', 'SUCCESS', 'OK', 'READY', 'FEASIBLE'].includes(s)) return 'ok'
  if (['RUNNING', 'FEASIBLE_PENDING'].includes(s)) return 'brand'
  if (['NO_EDGES', 'NO_DEMAND_DATA', 'SKIPPED', 'REORDER', 'EXCESS', 'WARNING'].includes(s)) return 'warn'
  if (['FAILED', 'INFEASIBLE', 'ERROR', 'UNHEALTHY', 'STOCKOUT_RISK', 'CRITICAL'].includes(s)) return 'danger'
  if (['HEALTHY'].includes(s)) return 'ok'
  return 'neutral'
}
