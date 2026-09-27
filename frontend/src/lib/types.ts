// Types mirroring backend/app/schemas/*.py. Kept hand-in-sync with the FastAPI
// backend since the backend does not currently publish a generated client.

export interface LocationOut {
  id: string
  name: string
  type: string
  region: string | null
  created_at: string | null
}

export interface ProductOut {
  id: string
  name: string
  sku: string | null
  category: string | null
  unit_cost: number | null
  created_at: string | null
}

export interface DemandRecord {
  location_id: string
  product_id: string
  date: string // YYYY-MM-DD
  quantity: number
}

export interface DemandIngestResponse {
  inserted_count: number
  updated_count: number
  ignored_count: number
  errors: string[]
}

export interface DemandHistoryOut {
  id: number
  location_id: string
  product_id: string
  date: string
  quantity: number
}

// ---- Optimization / GSM ----

export interface NodeInput {
  id: string
  type: string // "Supplier" | "DC" | "Store" | ...
  processing_time: number
  demand_mean?: number
  demand_std?: number
  holding_cost?: number
  max_s_out?: number
  min_s_out?: number
  service_level?: number
}

export interface EdgeInput {
  source: string
  target: string
  transit_time: number
  cost_per_unit?: number
  capacity?: number | null
}

export interface OptimizationRunRequest {
  run_type?: string
  nodes?: NodeInput[] | null
  edges?: EdgeInput[] | null
  max_service_time?: number
  node_capacities?: Record<string, number> | null
}

export interface NodeResult {
  s_in: number
  s_out: number
  net_replenishment_time: number
  safety_stock: number
  reorder_point: number
}

export interface OptimizationRunResponse {
  pipeline_run_id: string
  run_type: string
  status: string // "OPTIMAL" | "FEASIBLE" | "INVALID_DATA" | ...
  solver?: string
  fallback_used?: boolean
  objective_value?: number | null
  solver_duration_seconds?: number
  total_duration_seconds?: number
  capacity_violations?: string[]
  node_results?: Record<string, NodeResult>
  errors?: string[]
}

// ---- Forecasting ----

export interface ForecastItemInput {
  id: string
  history: number[]
  has_trend?: boolean
}

export interface ForecastRunRequest {
  items: ForecastItemInput[]
  horizon?: number
}

export interface ForecastItem {
  id: string
  forecast: number[]
  method: string // "SES" | "Holt-DES" | "Croston-SBA" | "ZERO"
  pattern: string // "smooth" | "intermittent" | "lumpy" | "erratic" | "INSUFFICIENT_DATA"
}

export interface ForecastRunResponse {
  forecasts: ForecastItem[]
  count: number
}

// ---- Full pipeline ----

export interface ItemHistoryInput {
  id: string
  history: number[]
  has_trend?: boolean
}

export interface PipelineRunRequest {
  run_type?: string
  nodes?: NodeInput[] | null
  edges?: EdgeInput[] | null
  items_history?: ItemHistoryInput[] | null
  horizon?: number
  max_service_time?: number
}

export interface PipelineStageForecast {
  status: string
  count?: number
}

export interface PipelineStageGsm {
  status: string
  solver?: string
}

export interface PipelineStageTransportation {
  status: string // "OPTIMAL" | "INFEASIBLE" | "NO_EDGES"
  total_cost?: number
  flows?: Record<string, number>
}

export interface PipelineRunResult {
  pipeline_run_id: string
  status: string // "SUCCESS" | "FAILED" | "RUNNING"
  error?: string
  stages?: {
    forecast?: PipelineStageForecast
    gsm?: PipelineStageGsm
    transportation?: PipelineStageTransportation
  }
}

export interface PipelineRunOut {
  id: string
  run_type: string
  status: string
  solver: string | null
  fallback_used: boolean
  started_at: string
  finished_at: string | null
  duration_seconds: number | null
  error: string | null
}

// ---- Lanes ----

export interface LaneOut {
  id: string
  source_id: string
  source_name: string
  source_type: string
  source_region: string | null
  target_id: string
  target_name: string
  target_type: string
  target_region: string | null
  transit_time: number
  cost_per_unit: number
  capacity: number | null
  created_at: string | null
}

// ---- Policies ----

export interface PolicyOut {
  id: string
  location_id: string
  location_name: string
  location_type: string
  product_id: string
  product_name: string
  product_sku: string | null
  service_level: number
  min_s_out: number
  max_s_out: number
  holding_cost: number
  ordering_cost: number
  review_period: number
  created_at: string | null
  updated_at: string | null
}

export interface PolicyUpdate {
  service_level?: number
  min_s_out?: number
  max_s_out?: number
  holding_cost?: number
  ordering_cost?: number
  review_period?: number
}

// ---- Dashboard summary ----

export interface LastRunOut {
  id: string
  status: string
  solver: string | null
  fallback_used: boolean
  started_at: string
}

export interface DashboardSummaryOut {
  inventory_value: number
  avg_service_level: number | null
  total_policies: number
  fill_rate: number | null
  at_risk_count: number
  measured_pairs: number
  open_alerts: number
  last_run: LastRunOut | null
}

// ---- Transportation plan ----

export interface LaneFlowOut {
  lane_id: string
  source_id: string
  source_name: string
  source_type: string
  target_id: string
  target_name: string
  target_type: string
  product_id: string
  sku: string | null
  product_name: string
  quantity: number
  capacity: number | null
  utilization: number | null
  transit_time: number | null
  cost: number
}

export interface TransportationPlanOut {
  status: string // "OPTIMAL" | "INFEASIBLE" | "NO_EDGES" | "NO_DEMAND_DATA"
  message?: string | null
  planned_units: number
  total_cost: number
  capacity_utilization: number | null
  active_lanes: number
  lane_flows: LaneFlowOut[]
}

// ---- Alerts ----

export interface AlertOut {
  id: number
  pipeline_run_id: string | null
  location_id: string | null
  product_id: string | null
  alert_type: string // "CAPACITY_EXCEEDED" | "TRANSPORT_INFEASIBLE" | ...
  severity: string // "INFO" | "WARNING" | "CRITICAL"
  message: string
  resolved: boolean
  created_at: string
}

// ---- API error shapes ----

export interface ApiValidationError {
  detail: 'Validation Error'
  errors: unknown[]
}

export interface ApiGenericError {
  detail: string
  message?: string
}

export interface ApiCodedError {
  detail: { code: string; message: string }
}
