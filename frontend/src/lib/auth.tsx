import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, getToken, SESSION_EXPIRED_EVENT, setToken } from '@/lib/api'
import { AuthContext, hasRole, type AuthContextValue, type Status } from '@/lib/auth-context'
import type { Role, UserOut } from '@/lib/types'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<UserOut | null>(null)
  const [status, setStatus] = useState<Status>(() => (getToken() ? 'loading' : 'signed-out'))
  const [sessionExpired, setSessionExpired] = useState(false)

  const signOut = useCallback(
    (expired: boolean) => {
      setToken(null)
      setUser(null)
      setStatus('signed-out')
      setSessionExpired(expired)
      queryClient.clear()
    },
    [queryClient],
  )

  // Restore the session on page load.
  useEffect(() => {
    if (!getToken()) return
    let cancelled = false
    api
      .me()
      .then((me) => {
        if (cancelled) return
        setUser(me)
        setStatus('signed-in')
      })
      .catch(() => {
        if (!cancelled) signOut(false)
      })
    return () => {
      cancelled = true
    }
  }, [signOut])

  useEffect(() => {
    const onExpired = () => signOut(true)
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired)
  }, [signOut])

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api.login(email, password)
      queryClient.clear()
      setToken(res.access_token)
      setUser(res.user)
      setSessionExpired(false)
      setStatus('signed-in')
    },
    [queryClient],
  )

  const refreshUser = useCallback(async () => {
    setUser(await api.me())
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      sessionExpired,
      login,
      logout: () => signOut(false),
      refreshUser,
      can: (minimum: Role) => hasRole(user, minimum),
    }),
    [user, status, sessionExpired, login, signOut, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
