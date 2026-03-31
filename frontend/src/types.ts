// ── Jobs ──────────────────────────────────────────────────────────────────────

export type Venture = "marketing_audit" | "content_studio" | "etsy"

export type JobStatus =
  | "pending"
  | "scraping" | "scraped"
  | "auditing" | "audited"
  | "generating_report" | "report_ready"
  | "transcribing" | "transcribed"
  | "generating" | "generated"
  | "packaging" | "packaged"
  | "delivering"
  | "review_pending" | "approved"
  | "delivered" | "published"
  | "failed" | "cancelled"

export interface Job {
  id: string
  venture: Venture
  status: JobStatus
  phase_current: number | null
  phase_total: number | null
  environment: string
  input_data: Record<string, unknown>
  output_data: Record<string, unknown>
  error_message: string | null
  celery_task_id: string | null
  created_at: string
  updated_at: string
  started_at: string | null
  completed_at: string | null
}

export interface JobListResponse {
  items: Job[]
  total: number
  page: number
  page_size: number
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export interface VentureStats {
  venture: string
  total_jobs: number
  pending: number
  in_progress: number
  completed: number
  failed: number
  pending_review: number
}

// Matches GET /api/platform/dashboard exactly
export interface DashboardStats {
  ventures: VentureStats[]
  total_cost_usd_month: number
  total_revenue_usd_month: number
  db_ok: boolean
  redis_ok: boolean
}

// ── Finance ───────────────────────────────────────────────────────────────────

export interface CostSummary {
  tool_id: string
  capability: string
  total_cost_usd: number
  call_count: number
}

export interface RevenueSummary {
  venture: string
  source: string
  total_amount_usd: number
  total_fee_usd: number
  total_net_usd: number
  order_count: number
}

// Matches GET /api/platform/finance exactly
export interface FinanceData {
  costs: CostSummary[]
  revenues: RevenueSummary[]
  net_usd: number
  period: string
}

// ── Health ────────────────────────────────────────────────────────────────────

// Matches GET /api/health exactly
export interface HealthData {
  status: string
  db: boolean
  redis: boolean
  version: string
}

// ── Settings ──────────────────────────────────────────────────────────────────

export interface ApiKey {
  service: string
  masked_key: string
  is_set: boolean
  last_tested: string | null
  test_ok: boolean | null
}

export interface ApiKeyTestResult {
  service: string
  ok: boolean
  detail: string
}

// ── Orders ────────────────────────────────────────────────────────────────────

export interface AuditOrderRequest {
  url: string
  tier: "snapshot" | "full" | "premium"
  report_type: "both" | "full" | "sample"
  client_email?: string
}

export interface PodcastOrderRequest {
  audio_url: string
  tier: "starter" | "standard" | "premium"
  show_name?: string
  client_email?: string
}

export interface OrderResponse {
  order_id: string
  celery_task_id: string
  status: string
}
