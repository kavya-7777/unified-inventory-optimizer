import { createContext, useContext } from 'react'
import type { Role, UserOut } from '@/lib/types'

const ROLE_RANK: Record<Role, number> = { viewer: 1, planner: 2, admin: 3 }

export const ROLE_LABEL: Record<Role, string> = {
  admin: 'Admin',
  planner: 'Planner',
  viewer: 'Viewer',
}

export const ROLE_DESCRIPTION: Record<Role, string> = {
  admin: 'Everything, plus managing users, loading demo data and the activity log',
  planner: 'View everything, run the pipeline, edit policies, resolve alerts, import data',
  viewer: 'Read-only access to dashboards, inventory, forecasts, plans and alerts',
}

export function hasRole(user: UserOut | null | undefined, minimum: Role): boolean {
  return !!user && ROLE_RANK[user.role] >= ROLE_RANK[minimum]
}

export type Status = 'loading' | 'signed-in' | 'signed-out'

export interface AuthContextValue {
  user: UserOut | null
  status: Status
  /** Set when the last session ended because it expired. */
  sessionExpired: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
  can: (minimum: Role) => boolean
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
