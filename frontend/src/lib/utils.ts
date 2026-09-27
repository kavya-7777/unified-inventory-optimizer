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

/** Format an ISO datetime string as a short, readable local date-time. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
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
  if (['INVALID_DATA', 'NO_EDGES', 'SKIPPED'].includes(s)) return 'warn'
  if (['FAILED', 'INFEASIBLE', 'ERROR', 'UNHEALTHY'].includes(s)) return 'danger'
  return 'neutral'
}
