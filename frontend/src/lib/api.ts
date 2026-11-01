import type {
  AlertOut,
  AuditEventOut,
  ImportRecord,
  ImportResult,
  LoginResponse,
  SetupStatus,
  UserCreate,
  UserOut,
  UserUpdate,
  DashboardSummaryOut,
  DemandForecastOut,
  DemandHistoryOut,
  DemandIngestResponse,
  DemandRecord,
  ForecastRunRequest,
  ForecastRunResponse,
  InventoryPositionsPage,
  LaneOut,
  LocationOut,
  NetworkRunAccepted,
  NetworkRunRequest,
  OptimizationRunRequest,
  OptimizationRunResponse,
  PipelineRunOut,
  PipelineRunRequest,
  PipelineRunResult,
  PolicyOut,
  PolicyUpdate,
  ProductOut,
  RunResultsPage,
  TransportationPlanOut,
} from './types'

export const API_BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) || 'http://localhost:8000'

// ── Session token ────────────────────────────────────────────────────────────
// Kept in localStorage so a refresh stays signed in; falls back to memory when storage
// is blocked (private windows, strict browser settings).
const TOKEN_KEY = 'uio.token'
let memoryToken: string | null = null

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? memoryToken
  } catch {
    return memoryToken
  }
}

export function setToken(token: string | null) {
  memoryToken = token
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // storage unavailable: the in-memory copy still works for this tab
  }
}

/** Fired when the server rejects the saved session (expired or deactivated). */
export const SESSION_EXPIRED_EVENT = 'uio:session-expired'

// ── Server wake-up tracking ──────────────────────────────────────────────────
// Free hosting puts the backend to sleep when idle; the first request can take up to a
// minute. Requests retry quietly while this is reported to the UI as "waking".
export type ServerState = 'ok' | 'waking'
const serverListeners = new Set<(s: ServerState) => void>()
let serverState: ServerState = 'ok'

function setServerState(next: ServerState) {
  if (next === serverState) return
  serverState = next
  serverListeners.forEach((fn) => fn(next))
}

export function subscribeServerState(fn: (s: ServerState) => void): () => void {
  serverListeners.add(fn)
  fn(serverState)
  return () => serverListeners.delete(fn)
}

const WAKE_TIMEOUT_MS = 90_000
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export class ApiError extends Error {
  status: number
  code?: string
  details?: unknown

  constructor(message: string, status: number, code?: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

/**
 * Normalizes the backend's several error-body shapes into a single ApiError:
 *  - 500 generic:        { detail: "Internal Server Error", message: string }
 *  - 422 validation:     { detail: "Validation Error", errors: [...] }
 *  - invalid network:    { detail: { code: "INVALID_NETWORK", message: string, errors: string[] } }
 *  - simple 404 etc:     { detail: string }
 */
async function parseErrorBody(res: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // not JSON — fall through with a generic message
  }

  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (detail && typeof detail === 'object' && 'code' in detail) {
      const coded = detail as { code: string; message: string }
      return new ApiError(coded.message, res.status, coded.code, body)
    }
    if (detail === 'Validation Error' && 'errors' in body) {
      const errors = (body as { errors: { loc?: unknown[]; msg?: string }[] }).errors
      const first = errors?.[0]
      const field = first?.loc ? String(first.loc[first.loc.length - 1]) : undefined
      const message = first?.msg ? `${field ? `${humanizeField(field)}: ` : ''}${first.msg}` : 'Check the submitted fields.'
      return new ApiError(message, res.status, 'VALIDATION_ERROR', body)
    }
    if (typeof detail === 'string') {
      const message = (body as { message?: string }).message
      return new ApiError(message ? `${detail}: ${message}` : detail, res.status, undefined, body)
    }
  }

  return new ApiError(`Request failed with status ${res.status}`, res.status, undefined, body)
}

function humanizeField(field: string): string {
  return field.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

interface RequestOptions extends RequestInit {
  /** Retry while the server is waking up. On by default for GET requests. */
  retryWhileWaking?: boolean
  /** Don't treat a 401 as an expired session (used by the login call). */
  skipSessionCheck?: boolean
}

async function send(path: string, init: RequestOptions = {}): Promise<Response> {
  const { retryWhileWaking, skipSessionCheck, ...fetchInit } = init
  const method = (fetchInit.method ?? 'GET').toUpperCase()
  const retry = retryWhileWaking ?? method === 'GET'
  const token = getToken()
  const isForm = fetchInit.body instanceof FormData
  const headers: Record<string, string> = {
    ...(isForm ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((fetchInit.headers as Record<string, string>) ?? {}),
  }

  const deadline = Date.now() + WAKE_TIMEOUT_MS
  let delay = 1500
  for (;;) {
    let res: Response | null = null
    try {
      res = await fetch(`${API_BASE_URL}${path}`, { ...fetchInit, headers })
    } catch (err) {
      // Network failure: the server is asleep, restarting or unreachable.
      if (!retry || Date.now() > deadline) {
        setServerState('ok')
        throw new ApiError(
          'Can’t reach the server. Check your connection and try again in a minute.',
          0,
          'NETWORK_ERROR',
          err,
        )
      }
    }
    if (res && ![502, 503, 504].includes(res.status)) {
      setServerState('ok')
      if (res.status === 401 && token && !skipSessionCheck) {
        setToken(null)
        window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
      }
      return res
    }
    if (res && (!retry || Date.now() > deadline)) {
      setServerState('ok')
      return res
    }
    setServerState('waking')
    await sleep(delay)
    delay = Math.min(delay * 1.5, 6000)
  }
}

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const res = await send(path, init)
  if (!res.ok) {
    throw await parseErrorBody(res)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/** Downloads a file endpoint (with the session token) and saves it in the browser. */
async function download(path: string, fallbackName: string): Promise<void> {
  const res = await send(path)
  if (!res.ok) throw await parseErrorBody(res)
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^";]+)"?/i.exec(disposition)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = match?.[1] ?? fallbackName
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function query(params: Record<string, string | number | undefined>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  // Auth & account
  login: (email: string, password: string) =>
    request<LoginResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
      retryWhileWaking: true,
      skipSessionCheck: true,
    }),
  me: () => request<UserOut>('/api/v1/auth/me'),
  changePassword: (current_password: string, new_password: string) =>
    request<void>('/api/v1/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
    }),

  // Users & activity (admin)
  listUsers: () => request<UserOut[]>('/api/v1/users'),
  createUser: (payload: UserCreate) =>
    request<UserOut>('/api/v1/users', { method: 'POST', body: JSON.stringify(payload) }),
  updateUser: (userId: string, payload: UserUpdate) =>
    request<UserOut>(`/api/v1/users/${userId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  resetUserPassword: (userId: string, new_password: string) =>
    request<void>(`/api/v1/users/${userId}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ new_password }),
    }),
  listAudit: (params: { action?: string; limit?: number; skip?: number } = {}) =>
    request<AuditEventOut[]>(`/api/v1/audit${query({ ...params })}`),

  // Setup, import & export
  getSetupStatus: () => request<SetupStatus>('/api/v1/setup/status'),
  loadDemoData: (reset: boolean) =>
    request<Record<string, number>>('/api/v1/admin/demo-data', {
      method: 'POST',
      body: JSON.stringify({ reset }),
    }),
  downloadTemplate: (includeData = false) =>
    download(
      `/api/v1/imports/template${includeData ? '?include_data=true' : ''}`,
      includeData ? 'inventory-data-current.xlsx' : 'inventory-import-template.xlsx',
    ),
  uploadImport: (file: File, dryRun: boolean) => {
    const body = new FormData()
    body.append('file', file)
    return request<ImportResult>(`/api/v1/imports?dry_run=${dryRun}`, { method: 'POST', body })
  },
  listImports: (limit = 20) => request<ImportRecord[]>(`/api/v1/imports${query({ limit })}`),
  downloadResults: () => download('/api/v1/exports/results', 'inventory-results.xlsx'),

  // Inventory
  listLocations: (skip = 0, limit = 100, type?: 'Supplier' | 'DC' | 'Store') =>
    request<LocationOut[]>(`/api/v1/locations${query({ skip, limit, type })}`),
  listProducts: (skip = 0, limit = 100) =>
    request<ProductOut[]>(`/api/v1/products${query({ skip, limit })}`),
  listLanes: () => request<LaneOut[]>('/api/v1/lanes'),
  getInventoryPositions: (
    params: { location_type?: string; status?: string; q?: string; skip?: number; limit?: number } = {},
  ) => request<InventoryPositionsPage>(`/api/v1/inventory/positions${query({ ...params })}`),

  // Policies
  listPolicies: (params: { q?: string; location_id?: string; skip?: number; limit?: number } = {}) =>
    request<PolicyOut[]>(`/api/v1/policies${query({ ...params })}`),
  updatePolicy: (policyId: string, payload: PolicyUpdate) =>
    request<PolicyOut>(`/api/v1/policies/${policyId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  // Dashboard
  getDashboardSummary: () => request<DashboardSummaryOut>('/api/v1/dashboard/summary'),

  // Transportation
  getTransportationPlan: (params: { product_id?: string; days?: number } = {}) =>
    request<TransportationPlanOut>(`/api/v1/transportation/plan${query({ ...params })}`),

  // Demand
  ingestDemand: (records: DemandRecord[]) =>
    request<DemandIngestResponse>('/api/v1/demand/ingest', {
      method: 'POST',
      body: JSON.stringify({ records }),
    }),
  getDemandHistory: (params: { location_id: string; product_id: string; start_date?: string; end_date?: string }) =>
    request<DemandHistoryOut[]>(`/api/v1/demand/history${query(params)}`),
  getDemandForecast: (params: { location_id: string; product_id: string; horizon?: number; history_days?: number }) =>
    request<DemandForecastOut>(`/api/v1/demand/forecast${query(params)}`),

  // Optimization
  runOptimization: (payload: OptimizationRunRequest) =>
    request<OptimizationRunResponse>('/api/v1/optimization/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  runForecast: (payload: ForecastRunRequest) =>
    request<ForecastRunResponse>('/api/v1/forecast/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  runPipeline: (payload: PipelineRunRequest) =>
    request<PipelineRunResult>('/api/v1/pipeline/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  runNetwork: (payload: NetworkRunRequest) =>
    request<NetworkRunAccepted>('/api/v1/network/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Runs
  listRuns: (limit = 10) => request<PipelineRunOut[]>(`/api/v1/runs${query({ limit })}`),
  getRun: (runId: string) => request<PipelineRunOut>(`/api/v1/runs/${runId}`),
  getRunResults: (runId: string, params: { product_id?: string; skip?: number; limit?: number } = {}) =>
    request<RunResultsPage>(`/api/v1/runs/${runId}/results${query({ ...params })}`),

  // Alerts
  listAlerts: (params: { resolved?: boolean; limit?: number } = {}) =>
    request<AlertOut[]>(
      `/api/v1/alerts${query({ resolved: params.resolved === undefined ? undefined : String(params.resolved), limit: params.limit })}`,
    ),
  resolveAlert: (alertId: number) =>
    request<AlertOut>(`/api/v1/alerts/${alertId}/resolve`, { method: 'POST' }),
}
