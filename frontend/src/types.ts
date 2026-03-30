export type Venture = "marketing_audit" | "content_studio" | "etsy"

export type JobStatus =
  | "pending"
  | "scraping"
  | "scraped"
  | "auditing"
  | "audited"
  | "generating_report"
  | "report_ready"
  | "review_pending"
  | "approved"
  | "delivering"
  | "delivered"
  | "failed"
  | "transcribing"
  | "transcribed"
  | "generating"
  | "generated"
  | "packaging"
  | "packaged"
  | "completed"

export interface Job {
  id: string
  venture: Venture
  status: JobStatus
  phase_current: number | null
  phase_total: number | null
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

export interface DashboardStats {
  active_jobs: number
  pending_reviews: number
  monthly_revenue: number
  api_spend: number
  jobs_in_flight: Job[]
  review_queue: Job[]
  system_health: SystemHealth
}

export interface SystemHealth {
  status: "healthy" | "degraded" | "down"
  services: ServiceHealth[]
  checked_at: string
}

export interface ServiceHealth {
  name: string
  status: "healthy" | "degraded" | "down"
  latency_ms?: number
  message?: string
}

export interface FinanceData {
  revenue_by_venture: RevenueEntry[]
  cost_by_tool: CostEntry[]
  pnl: PnlSummary
}

export interface RevenueEntry {
  venture: string
  total_revenue: number
  order_count: number
  period: string
}

export interface CostEntry {
  tool: string
  total_cost: number
  call_count: number
  period: string
}

export interface PnlSummary {
  gross_revenue: number
  total_costs: number
  net_profit: number
  margin_pct: number
  period: string
}

export interface HealthData {
  status: "healthy" | "degraded" | "down"
  version: string
  environment: string
  services: ServiceHealth[]
  checked_at: string
}

export interface AuditOrderRequest {
  url: string
  tier: "snapshot" | "full" | "full_strategy"
  client_email: string
  report_type: "full_and_sample" | "full_only" | "sample_only"
}

export interface PodcastOrderRequest {
  audio_url: string
  tier: "starter" | "standard" | "premium"
  show_name: string
  client_email: string
}

export interface OrderResponse {
  job_id: string
  status: JobStatus
  message: string
}

export interface ApiKey {
  service: string
  masked_value: string
  last_tested: string | null
  test_status: "ok" | "failed" | "untested"
}

export interface ApiKeyTestResult {
  service: string
  status: "ok" | "failed"
  message: string
}

export interface Settings {
  keys?: ApiKey[]
  notifications?: NotificationSettings
  environment?: Record<string, string>
}

export interface NotificationSettings {
  slack_webhook: string
  email_on_failure: boolean
  email_on_review: boolean
}
