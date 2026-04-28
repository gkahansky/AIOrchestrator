// ── Jobs ──────────────────────────────────────────────────────────────────────

export type Venture = "marketing_audit" | "content_studio" | "etsy" | "accessibility_audit" | "content_repurposing"

export type JobStatus =
  | "pending"
  | "running"
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

// ── Content Repurposing ───────────────────────────────────────────────────────

export interface CRJobSummary {
  id: string
  status: string
  plan: string
  show_name: string | null
  episode_title: string | null
  clip_count: number | null
  error_message: string | null
  created_at: string
}

// ── Content Repurposing Detail ────────────────────────────────────────────────

export interface CRClipAsset {
  id: number
  clip_index: number
  start_s: number
  end_s: number
  virality_score: number | null
  hook: string | null
  drive_clip_id: string | null
  drive_thumbnail_id: string | null
  title: string | null
  platform: string | null
  created_at: string
}

export interface CRJobDetail {
  id: string
  status: string
  plan: string
  show_name: string | null
  episode_title: string | null
  client_email: string | null
  drive_folder_id: string | null
  clip_count: number | null
  video_duration_s: number | null
  error_message: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
  clips: CRClipAsset[]
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
  is_testing?: boolean
}

export interface AccessibilityAuditRequest {
  url: string
  client_id?: string
  client_email?: string
  is_testing?: boolean
  is_bundled?: boolean
  tier?: "single_page" | "sample" | "standard" | "premium"
}

export interface PodcastOrderRequest {
  audio: File
  service_type: "show_notes" | "repurposing_pack"
  tier: "starter" | "standard" | "premium" | "pro"
  client_email?: string
  show_name?: string
  episode_title?: string
  host_name?: string
  guest_name?: string
  special_instructions?: string
  niche?: string
  audience?: string
  show_url?: string
  guest_expertise?: string
  competitor_urls?: string
  show_concept?: string
  host_background?: string
  launch_type?: "new" | "relaunch"
  bundle_sku?: string
  add_ons?: string
}

export interface OrderResponse {
  job_id: string        // DB UUID — use for /jobs/{job_id} navigation
  order_id: string
  celery_task_id: string
  status: string
}

export interface AdvisoryProposal {
  id: string
  advisor_id: string
  category: string
  content: string | Record<string, unknown>
  status: string
  priority: number
  job_id: string | null
  created_at: string
}

// ── Strategy Chat ─────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  advisor_id?: string   // set on assistant messages
  content: string
  ts: number
}

export interface ChatSession {
  id: string
  name: string
  advisor_ids: string[]
  messages: ChatMessage[]
  loading: boolean
}

export interface ChatRequest {
  advisor_ids: string[]
  messages: Pick<ChatMessage, "role" | "advisor_id" | "content">[]
}

export interface ChatApiResponse {
  responses: { advisor_id: string; content: string }[]
}

export type RoadmapItemType = "New feature" | "Bug" | "Feature enhancement"

export type RoadmapStatus =
  | "not_started"
  | "in_progress"
  | "in_testing"
  | "ready_for_deployment"
  | "done"

export interface RoadmapFeature {
  id: number
  name: string
  created_at: string
}

export interface RoadmapItem {
  id: number
  title: string
  description: string
  item_type: RoadmapItemType | null
  feature_id: number | null
  feature_name: string | null
  status: RoadmapStatus
  sort_order: number
  completed_at: string | null
  created_at: string
}

export interface RoadmapListResponse {
  backlog: RoadmapItem[]
  wip: RoadmapItem[]
}

export interface RoadmapItemCreate {
  title: string
  description: string
  item_type: RoadmapItemType
  feature_id: number | null
  status: RoadmapStatus
}

export interface RoadmapItemUpdate {
  title?: string
  description?: string
  item_type?: RoadmapItemType
  feature_id?: number | null
  status?: RoadmapStatus
}

export interface AdvisorConfig {
  id: string
  model: string
  capabilities: string[]
  prompt_ref: string
  system_prompt: string
}
