import type {
  AlertOut,
  DemandHistoryOut,
  DemandIngestResponse,
  DemandRecord,
  ForecastRunRequest,
  ForecastRunResponse,
  LocationOut,
  OptimizationRunRequest,
  OptimizationRunResponse,
  PipelineRunOut,
  PipelineRunRequest,
  PipelineRunResult,
  ProductOut,
} from './types'

export const API_BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) || 'http://localhost:8000'

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
 *  - solver/pipeline:    { detail: { code: "SOLVER_ERROR"|"PIPELINE_ERROR", message: string } }
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
      return new ApiError('Validation error — check the submitted fields.', res.status, 'VALIDATION_ERROR', body)
    }
    if (typeof detail === 'string') {
      const message = (body as { message?: string }).message
      return new ApiError(message ? `${detail}: ${message}` : detail, res.status, undefined, body)
    }
  }

  return new ApiError(`Request failed with status ${res.status}`, res.status, undefined, body)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })

  if (!res.ok) {
    throw await parseErrorBody(res)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
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
  healthReady: () => request<{ status: string; detail?: string }>('/health/ready'),

  // Inventory
  listLocations: (skip = 0, limit = 100) =>
    request<LocationOut[]>(`/api/v1/locations${query({ skip, limit })}`),
  listProducts: (skip = 0, limit = 100) =>
    request<ProductOut[]>(`/api/v1/products${query({ skip, limit })}`),

  // Demand
  ingestDemand: (records: DemandRecord[]) =>
    request<DemandIngestResponse>('/api/v1/demand/ingest', {
      method: 'POST',
      body: JSON.stringify({ records }),
    }),
  getDemandHistory: (params: { location_id: string; product_id: string; start_date?: string; end_date?: string }) =>
    request<DemandHistoryOut[]>(`/api/v1/demand/history${query(params)}`),

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

  // Runs
  listRuns: (limit = 10) => request<PipelineRunOut[]>(`/api/v1/runs${query({ limit })}`),
  getRun: (runId: string) => request<PipelineRunOut>(`/api/v1/runs/${runId}`),

  // Alerts
  listAlerts: (params: { resolved?: boolean; limit?: number } = {}) =>
    request<AlertOut[]>(
      `/api/v1/alerts${query({ resolved: params.resolved === undefined ? undefined : String(params.resolved), limit: params.limit })}`,
    ),
  resolveAlert: (alertId: number) =>
    request<AlertOut>(`/api/v1/alerts/${alertId}/resolve`, { method: 'POST' }),
}
