import type {
  Job,
  JobListResponse,
  DashboardStats,
  FinanceData,
  HealthData,
  AuditOrderRequest,
  PodcastOrderRequest,
  OrderResponse,
  ApiKey,
  ApiKeyTestResult,
  AdvisoryProposal,
  AdvisorConfig,
  AppUser,
  RoadmapFeature,
  RoadmapItem,
  RoadmapListResponse,
  RoadmapItemCreate,
  RoadmapItemUpdate,
  ChatRequest,
  ChatApiResponse,
  CRJobSummary,
  CRJobDetail,
} from "./types"

const BASE = import.meta.env.VITE_API_URL || "https://api.planbadmin.com"

export function getHeaders(): HeadersInit {
  const token = localStorage.getItem("api_token") ?? "test"
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `HTTP ${res.status}: ${res.statusText}`
    try {
      const body = await res.json()
      const detail = body.detail ?? body.message
      // FastAPI validation errors return detail as an array of error objects
      if (Array.isArray(detail)) {
        message = detail.map((e: { msg?: string; loc?: string[] }) =>
          [e.loc?.slice(1).join("."), e.msg].filter(Boolean).join(": ")
        ).join("; ")
      } else if (typeof detail === "string") {
        message = detail
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

export async function fetchJobs(params?: {
  venture?: string
  status?: string
  page?: number
  page_size?: number
}): Promise<JobListResponse> {
  const url = new URL(`${BASE}/api/jobs`)
  if (params?.venture) url.searchParams.set("venture", params.venture)
  if (params?.status) url.searchParams.set("status", params.status)
  if (params?.page) url.searchParams.set("page", String(params.page))
  if (params?.page_size) url.searchParams.set("page_size", String(params.page_size))

  const res = await fetch(url.toString(), { headers: getHeaders() })
  return handleResponse<JobListResponse>(res)
}

export async function fetchJob(id: string): Promise<Job> {
  const res = await fetch(`${BASE}/api/jobs/${id}`, { headers: getHeaders() })
  return handleResponse<Job>(res)
}

export async function approveJob(id: string, notes?: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/api/jobs/${id}/approve`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ notes }),
  })
  return handleResponse<{ message: string }>(res)
}

export async function rejectJob(id: string, notes?: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/api/jobs/${id}/reject`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ notes }),
  })
  return handleResponse<{ message: string }>(res)
}

export async function retryJob(id: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/api/jobs/${id}/retry`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<{ message: string }>(res)
}

export async function cancelJob(id: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/api/jobs/${id}/cancel`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<{ message: string }>(res)
}

export async function fetchDashboard(): Promise<DashboardStats> {
  const res = await fetch(`${BASE}/api/platform/dashboard`, { headers: getHeaders() })
  return handleResponse<DashboardStats>(res)
}

export async function fetchFinance(): Promise<FinanceData> {
  const res = await fetch(`${BASE}/api/platform/finance`, { headers: getHeaders() })
  return handleResponse<FinanceData>(res)
}

export async function fetchHealth(): Promise<HealthData> {
  const res = await fetch(`${BASE}/api/health`, { headers: getHeaders() })
  return handleResponse<HealthData>(res)
}

export async function createAuditOrder(data: AuditOrderRequest): Promise<OrderResponse> {
  const res = await fetch(`${BASE}/api/ventures/marketing-audit/orders`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(data),
  })
  return handleResponse<OrderResponse>(res)
}

export async function createAccessibilityAudit(data: import("./types").AccessibilityAuditRequest): Promise<{ audit_id: string, detail: string }> {
  const res = await fetch(`${BASE}/api/audit/accessibility/initiate`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({
      url: data.url,
      tier: data.tier,
      client_id: data.client_id ?? data.client_email,
      client_email: data.client_email ?? data.client_id,
      is_testing: data.is_testing,
      is_bundled: data.is_bundled
    }),
  })
  return handleResponse<{ audit_id: string, detail: string }>(res)
}

export async function fetchAccessibilityAudits(): Promise<any> {
  const res = await fetch(`${BASE}/api/audit/accessibility/`, {
    method: "GET",
    headers: getHeaders(),
  })
  return handleResponse<any>(res)
}

// ── Security Audit ─────────────────────────────────────────────────────────────

export interface SecurityAuditOrderRequest {
  url: string
  tier: "starter" | "professional" | "agency"
  client_email?: string
  verification_email?: string
  is_testing?: boolean
  tos_accepted?: boolean
  auth_username?: string
  auth_password?: string
  auth_login_url?: string
}

export async function createSecurityAuditOrder(
  data: SecurityAuditOrderRequest,
): Promise<{ audit_id: string; job_id: string; scope_token: string; scope_dns_record: string; status: string }> {
  const res = await fetch(`${BASE}/api/ventures/security-audit/orders`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(data),
  })
  return handleResponse(res)
}

export async function fetchSecurityAuditOrders(): Promise<any[]> {
  const res = await fetch(`${BASE}/api/ventures/security-audit/orders`, {
    headers: getHeaders(),
  })
  return handleResponse(res)
}

export async function fetchSecurityAuditOrder(auditId: string): Promise<any> {
  const res = await fetch(`${BASE}/api/ventures/security-audit/orders/${auditId}`, {
    headers: getHeaders(),
  })
  return handleResponse(res)
}

export async function verifyScopeSecurityAudit(
  auditId: string,
): Promise<{ audit_id: string; verified: boolean; method: string | null; reason: string | null }> {
  const res = await fetch(
    `${BASE}/api/ventures/security-audit/orders/${auditId}/verify-scope`,
    { method: "POST", headers: getHeaders() },
  )
  return handleResponse(res)
}

export async function approveScopeSecurityAudit(auditId: string): Promise<any> {
  const res = await fetch(
    `${BASE}/api/ventures/security-audit/orders/${auditId}/approve-scope`,
    { method: "POST", headers: getHeaders() },
  )
  return handleResponse(res)
}

export async function reviewSecurityAuditOrder(
  auditId: string,
  action: "approve" | "reject",
  notes?: string,
): Promise<any> {
  const res = await fetch(
    `${BASE}/api/ventures/security-audit/orders/${auditId}/review`,
    {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ action, notes }),
    },
  )
  return handleResponse(res)
}

export async function deliverSecurityAuditOrder(auditId: string, notes?: string): Promise<any> {
  const res = await fetch(
    `${BASE}/api/ventures/security-audit/orders/${auditId}/deliver`,
    {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ notes }),
    },
  )
  return handleResponse(res)
}

export async function resendVerificationEmail(auditId: string): Promise<any> {
  const res = await fetch(
    `${BASE}/api/ventures/security-audit/orders/${auditId}/resend-verification-email`,
    { method: "POST", headers: getHeaders() },
  )
  return handleResponse(res)
}

export async function createPodcastOrder(data: PodcastOrderRequest): Promise<OrderResponse> {
  const token = localStorage.getItem("api_token") ?? "test"
  const formData = new FormData()
  formData.append("audio", data.audio)
  formData.append("service_type", data.service_type)
  formData.append("tier", data.tier)
  if (data.client_email) formData.append("client_email", data.client_email)
  if (data.show_name) formData.append("show_name", data.show_name)
  if (data.episode_title) formData.append("episode_title", data.episode_title)
  if (data.host_name) formData.append("host_name", data.host_name)
  if (data.guest_name) formData.append("guest_name", data.guest_name)
  if (data.special_instructions) formData.append("special_instructions", data.special_instructions)
  if (data.niche) formData.append("niche", data.niche)
  if (data.audience) formData.append("audience", data.audience)
  if (data.show_url) formData.append("show_url", data.show_url)
  if (data.guest_expertise) formData.append("guest_expertise", data.guest_expertise)
  if (data.competitor_urls) formData.append("competitor_urls", data.competitor_urls)
  if (data.show_concept) formData.append("show_concept", data.show_concept)
  if (data.host_background) formData.append("host_background", data.host_background)
  if (data.launch_type) formData.append("launch_type", data.launch_type)
  if (data.bundle_sku) formData.append("bundle_sku", data.bundle_sku)
  if (data.add_ons) formData.append("add_ons", data.add_ons)
  const res = await fetch(`${BASE}/api/ventures/content-studio/orders`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  })
  return handleResponse<OrderResponse>(res)
}

export async function fetchAuditOrders(params?: {
  page?: number
  page_size?: number
}): Promise<JobListResponse> {
  const url = new URL(`${BASE}/api/ventures/marketing-audit/orders`)
  if (params?.page) url.searchParams.set("page", String(params.page))
  if (params?.page_size) url.searchParams.set("page_size", String(params.page_size))
  const res = await fetch(url.toString(), { headers: getHeaders() })
  return handleResponse<JobListResponse>(res)
}

export async function createCRJob(data: {
  plan: string
  video: File
  show_name?: string
  episode_title?: string
  host_name?: string
  guest_name?: string
  client_email?: string
  niche?: string
  audience?: string
  brand_voice?: string
  clip_instructions?: string
}): Promise<{ job_id: string; status: string; message: string }> {
  const token = localStorage.getItem("api_token") ?? "test"
  const form = new FormData()
  form.append("plan", data.plan)
  form.append("video", data.video)
  if (data.show_name)          form.append("show_name",          data.show_name)
  if (data.episode_title)      form.append("episode_title",      data.episode_title)
  if (data.host_name)          form.append("host_name",          data.host_name)
  if (data.guest_name)         form.append("guest_name",         data.guest_name)
  if (data.client_email)       form.append("client_email",       data.client_email)
  if (data.niche)              form.append("niche",              data.niche)
  if (data.audience)           form.append("audience",           data.audience)
  if (data.brand_voice)        form.append("brand_voice",        data.brand_voice)
  if (data.clip_instructions)  form.append("clip_instructions",  data.clip_instructions)
  const res = await fetch(`${BASE}/api/ventures/content-repurposing/jobs`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },   // no Content-Type — browser sets multipart boundary
    body: form,
  })
  return handleResponse(res)
}

export async function fetchCRJobs(): Promise<CRJobSummary[]> {
  const res = await fetch(`${BASE}/api/ventures/content-repurposing/jobs`, { headers: getHeaders() })
  return handleResponse(res)
}

export async function fetchCRJob(jobId: string): Promise<CRJobDetail> {
  const res = await fetch(`${BASE}/api/ventures/content-repurposing/jobs/${jobId}`, { headers: getHeaders() })
  return handleResponse<CRJobDetail>(res)
}

export async function approveCRJob(jobId: string): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${BASE}/api/ventures/content-repurposing/jobs/${jobId}/approve`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse(res)
}

export async function retryCRJob(jobId: string): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${BASE}/api/ventures/content-repurposing/jobs/${jobId}/retry`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse(res)
}

export async function cancelCRJob(jobId: string): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${BASE}/api/ventures/content-repurposing/jobs/${jobId}/cancel`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse(res)
}

export async function approveCRJobChapters(
  jobId: string,
  selectedIds: number[] | null,
): Promise<{ job_id: string; status: string; message: string }> {
  const res = await fetch(
    `${BASE}/api/ventures/content-repurposing/jobs/${jobId}/chapters/approve`,
    {
      method: "POST",
      headers: { ...getHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ selected_ids: selectedIds }),
    },
  )
  return handleResponse(res)
}

export async function fetchPodcastOrders(params?: {
  page?: number
  page_size?: number
}): Promise<JobListResponse> {
  const url = new URL(`${BASE}/api/ventures/content-studio/orders`)
  if (params?.page) url.searchParams.set("page", String(params.page))
  if (params?.page_size) url.searchParams.set("page_size", String(params.page_size))
  const res = await fetch(url.toString(), { headers: getHeaders() })
  return handleResponse<JobListResponse>(res)
}

export async function fetchApiKeys(): Promise<{ keys: ApiKey[] }> {
  const res = await fetch(`${BASE}/api/platform/settings/keys`, { headers: getHeaders() })
  return handleResponse<{ keys: ApiKey[] }>(res)
}

export async function testApiKey(service: string): Promise<ApiKeyTestResult> {
  const res = await fetch(`${BASE}/api/platform/settings/keys/${service}/test`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<ApiKeyTestResult>(res)
}

export async function updateApiKey(service: string, value: string): Promise<ApiKey> {
  const res = await fetch(`${BASE}/api/platform/settings/keys/${service}`, {
    method: "PUT",
    headers: getHeaders(),
    body: JSON.stringify({ key: value }),
  })
  return handleResponse<ApiKey>(res)
}

// ── Strategy Room ──────────────────────────────────────────────────────────────

export async function fetchProposals(params?: { status?: string; advisor_id?: string }): Promise<AdvisoryProposal[]> {
  const url = new URL(`${BASE}/api/platform/strategy/proposals`)
  url.searchParams.set("status", params?.status ?? "pending_review")
  if (params?.advisor_id) url.searchParams.set("advisor_id", params.advisor_id)
  const res = await fetch(url.toString(), { headers: getHeaders() })
  return handleResponse<AdvisoryProposal[]>(res)
}

export async function approveProposal(id: string): Promise<AdvisoryProposal> {
  const res = await fetch(`${BASE}/api/platform/strategy/proposals/${id}/approve`, {
    method: "POST",
    headers: getHeaders(),
  })
  if (!res.ok) throw new Error("Failed to approve proposal")
  return res.json()
}

export async function rejectProposal(id: string): Promise<AdvisoryProposal> {
  const res = await fetch(`${BASE}/api/platform/strategy/proposals/${id}/reject`, {
    method: "POST",
    headers: getHeaders(),
  })
  if (!res.ok) throw new Error("Failed to reject proposal")
  return res.json()
}

export async function fetchAdvisors(): Promise<AdvisorConfig[]> {
  const res = await fetch(`${BASE}/api/platform/strategy/advisors`, { headers: getHeaders() })
  if (!res.ok) throw new Error("Failed to fetch advisors")
  return res.json()
}

export async function updateAdvisorPrompt(id: string, content: string): Promise<void> {
  const res = await fetch(`${BASE}/api/platform/strategy/advisors/${id}/prompt`, {
    method: "PUT",
    headers: getHeaders(),
    body: JSON.stringify({ content }),
  })
  if (!res.ok) throw new Error("Failed to update advisor prompt")
}

// ── Auth / Users ─────────────────────────────────────────────────────────────

export async function fetchUsers(): Promise<AppUser[]> {
  const res = await fetch(`${BASE}/api/auth/users`, { headers: getHeaders() })
  return handleResponse<AppUser[]>(res)
}

// ── Roadmap ──────────────────────────────────────────────────────────────────

export async function fetchRoadmap(): Promise<RoadmapListResponse> {
  const res = await fetch(`${BASE}/api/platform/strategy/roadmap`, { headers: getHeaders() })
  return handleResponse<RoadmapListResponse>(res)
}

export async function fetchRoadmapDone(): Promise<RoadmapItem[]> {
  const res = await fetch(`${BASE}/api/platform/strategy/roadmap/done`, { headers: getHeaders() })
  return handleResponse<RoadmapItem[]>(res)
}

export async function fetchRoadmapFeatures(): Promise<RoadmapFeature[]> {
  const res = await fetch(`${BASE}/api/platform/strategy/roadmap/features`, { headers: getHeaders() })
  return handleResponse<RoadmapFeature[]>(res)
}

export async function createRoadmapFeature(name: string): Promise<RoadmapFeature> {
  const res = await fetch(`${BASE}/api/platform/strategy/roadmap/features`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ name }),
  })
  return handleResponse<RoadmapFeature>(res)
}

export async function createRoadmapItem(data: RoadmapItemCreate): Promise<RoadmapItem> {
  const res = await fetch(`${BASE}/api/platform/strategy/roadmap`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(data),
  })
  return handleResponse<RoadmapItem>(res)
}

export async function updateRoadmapItem(id: number, data: RoadmapItemUpdate): Promise<RoadmapItem> {
  const res = await fetch(`${BASE}/api/platform/strategy/roadmap/${id}`, {
    method: "PUT",
    headers: getHeaders(),
    body: JSON.stringify(data),
  })
  return handleResponse<RoadmapItem>(res)
}

export async function deleteRoadmapItem(id: number): Promise<void> {
  const res = await fetch(`${BASE}/api/platform/strategy/roadmap/${id}`, {
    method: "DELETE",
    headers: getHeaders(),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export async function reorderRoadmapItems(ids: number[]): Promise<void> {
  const res = await fetch(`${BASE}/api/platform/strategy/roadmap/reorder`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ ids }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export async function fetchAdvisorRuns(limit = 20): Promise<AdvisoryProposal[]> {
  const res = await fetch(`${BASE}/api/platform/strategy/advisors/runs?limit=${limit}`, {
    headers: getHeaders(),
  })
  return handleResponse<AdvisoryProposal[]>(res)
}

export async function fetchAdvisorDiagnostics(): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/api/platform/strategy/advisors/diagnostics`, {
    headers: getHeaders(),
  })
  return handleResponse<Record<string, unknown>>(res)
}

export async function triggerAdvisor(advisorId: string): Promise<{ status: string; proposal?: { id: string; category: string; priority: number } }> {
  const res = await fetch(`${BASE}/api/platform/strategy/advisors/${advisorId}/trigger`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<{ status: string; proposal?: { id: string; category: string; priority: number } }>(res)
}

// ── Admin / Maintenance ───────────────────────────────────────────────────────

export interface CleanupResult {
  deleted_count: number
  error_count: number
  dry_run: boolean
  cutoff_date: string
  folders_checked: string[]
  deleted: { file_id: string; name: string; modified: string; folder_id: string; action: string }[]
  errors: string[]
}

export async function previewDriveCleanup(maxAgeDays = 30): Promise<CleanupResult> {
  const url = new URL(`${BASE}/api/platform/admin/cleanup-drive/preview`)
  url.searchParams.set("max_age_days", String(maxAgeDays))
  const res = await fetch(url.toString(), { headers: getHeaders() })
  return handleResponse<CleanupResult>(res)
}

export async function runDriveCleanup(maxAgeDays = 30): Promise<CleanupResult> {
  const url = new URL(`${BASE}/api/platform/admin/cleanup-drive`)
  url.searchParams.set("max_age_days", String(maxAgeDays))
  const res = await fetch(url.toString(), { method: "POST", headers: getHeaders() })
  return handleResponse<CleanupResult>(res)
}

export async function chatWithAdvisors(body: ChatRequest): Promise<ChatApiResponse> {
  const res = await fetch(`${BASE}/api/platform/strategy/chat`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(body),
  })
  return handleResponse<ChatApiResponse>(res)
}

// ── Market Research ───────────────────────────────────────────────────────────

export interface MarketResearchSession {
  id: string
  topic: string
  title: string | null
  status: string
  selected_llms: string[]
  critic_llm: string
  drive_link: string | null
  created_at: string
}

export interface WorkPackage {
  id: string
  name: string
  scope: string
  sections: string[]
}

export interface PackageResult {
  name: string
  scope: string
  sections: string[]
  merged: string
}

export interface V2OptimizedPrompts {
  version: 2
  packages: WorkPackage[]
}

export interface V2ResearchResults {
  version: 2
  packages: Record<string, PackageResult>
  total: number
}

// ── V3 Section-Based types ────────────────────────────────────────────────────

export type V3SectionStatus =
  | 'pending'
  | 'drafting'
  | 'merging'
  | 'reviewing_1'
  | 'reviewing_2'
  | 'done'
  | 'disclaimer'

export interface V3SectionResult {
  name: string
  status: V3SectionStatus
  draft: string
  citations: string[]
  summary: string
  critic_round_1?: {
    verdict: 'PASS' | 'REVISE'
    missing_items: string[]
    uncited_claims: string[]
    gaps_summary: string
  } | null
  critic_round_2?: {
    verdict: 'PASS' | 'REVISE'
    missing_items: string[]
    uncited_claims: string[]
    gaps_summary: string
  } | null
}

export interface V3ResearchResults {
  version: 3
  sections: Record<string, V3SectionResult>
}

export interface SectionLibraryEntry {
  id: string
  name: string
  required_items: string[]
  expected_outputs: string[]
  default_prompt: string
  default_enabled: boolean
  locked: boolean
}

export interface SectionConfigEntry {
  id: string
  name: string
  enabled: boolean
  prompt: string
  locked: boolean
  required_items: string[]
  expected_outputs: string[]
}

export interface SectionConfig {
  version: 3
  system_prompt: string
  sections: SectionConfigEntry[]
}

export interface MarketResearchDetail extends MarketResearchSession {
  section_config: SectionConfig | null
  optimized_prompts: Record<string, string> | V2OptimizedPrompts | null
  research_results: Record<string, string> | V2ResearchResults | V3ResearchResults | null
  merged_report: string | null
  critic_feedback: string | null
  final_report: string | null
  error: string | null
}

export interface MarketResearchHistorySection {
  id: string
  name: string
  enabled: boolean
  prompt: string
}

export interface MarketResearchHistory {
  session_id: string
  topic: string
  title: string | null
  status: string
  selected_llms: string[]
  system_prompt: string | null
  sections: MarketResearchHistorySection[]
  uploaded_files: string[]
  started_at: string | null
  completed_at: string | null
  duration_s: number | null
  error: string | null
  drive_link: string | null
  created_at: string
}

export interface SectionDetail {
  section_id: string
  name: string
  status: V3SectionStatus
  draft: string
  citations: string[]
  summary: string
  critic_round_1: V3SectionResult['critic_round_1']
  critic_round_2: V3SectionResult['critic_round_2']
  required_items: string[]
  expected_outputs: string[]
}

export async function fetchAvailableLlms(): Promise<{ available: string[] }> {
  const res = await fetch(`${BASE}/api/ventures/market-research/available-llms`, { headers: getHeaders() })
  return handleResponse<{ available: string[] }>(res)
}

export async function fetchSectionLibrary(): Promise<{ sections: SectionLibraryEntry[]; default_system_prompt: string }> {
  const res = await fetch(`${BASE}/api/ventures/market-research/section-library`, { headers: getHeaders() })
  return handleResponse(res)
}

export async function fetchSectionDetail(sessionId: string, sectionId: string): Promise<SectionDetail> {
  const res = await fetch(
    `${BASE}/api/ventures/market-research/sessions/${sessionId}/sections/${sectionId}`,
    { headers: getHeaders() },
  )
  return handleResponse<SectionDetail>(res)
}

export async function fetchSectorLibrary(sector: string): Promise<{ sections: SectionLibraryEntry[]; default_system_prompt: string }> {
  const res = await fetch(`${BASE}/api/ventures/market-research/sector-library/${sector}`, { headers: getHeaders() })
  return handleResponse(res)
}

export async function fetchProducts(): Promise<{ products: Record<string, { display_name: string; sectors: string[]; default_sector: string }>; sectors: Record<string, { display_name: string; description: string }> }> {
  const res = await fetch(`${BASE}/api/ventures/market-research/products`, { headers: getHeaders() })
  return handleResponse(res)
}

export async function createMarketResearchSession(body: {
  topic: string
  selected_llms?: string[]
  critic_llm?: string
  client_email?: string
  section_config?: SectionConfig | null
  report_config?: {
    output_depth?: string
    writing_style?: string
    framework?: string
    citation_format?: string
  } | null
  sector?: string | null
}): Promise<MarketResearchSession> {
  const res = await fetch(`${BASE}/api/ventures/market-research/sessions`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(body),
  })
  return handleResponse<MarketResearchSession>(res)
}

export async function uploadResearchDocs(sessionId: string, files: File[]): Promise<{ ingested: { filename: string; chunks: number }[]; total_chunks: number }> {
  const form = new FormData()
  files.forEach(f => form.append("files", f))
  const res = await fetch(`${BASE}/api/ventures/market-research/sessions/${sessionId}/upload`, {
    method: "POST",
    headers: { Authorization: (getHeaders() as Record<string, string>).Authorization },
    body: form,
  })
  return handleResponse(res)
}

export async function fetchMarketResearchSessions(): Promise<MarketResearchSession[]> {
  const res = await fetch(`${BASE}/api/ventures/market-research/sessions`, { headers: getHeaders() })
  return handleResponse<MarketResearchSession[]>(res)
}

export async function fetchMarketResearchSession(id: string): Promise<MarketResearchDetail> {
  const res = await fetch(`${BASE}/api/ventures/market-research/sessions/${id}`, { headers: getHeaders() })
  return handleResponse<MarketResearchDetail>(res)
}

export async function fetchResearchHistory(id: string): Promise<MarketResearchHistory> {
  const res = await fetch(`${BASE}/api/ventures/market-research/sessions/${id}/history`, { headers: getHeaders() })
  return handleResponse<MarketResearchHistory>(res)
}

export async function rerunResearchSession(
  sessionId: string,
  adjustedPrompts: Record<string, string>,
  selectedLlms?: string[],
  criticLlm?: string,
): Promise<MarketResearchSession> {
  const res = await fetch(`${BASE}/api/ventures/market-research/sessions/${sessionId}/rerun`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ adjusted_prompts: adjustedPrompts, selected_llms: selectedLlms, critic_llm: criticLlm }),
  })
  return handleResponse<MarketResearchSession>(res)
}

export async function retryResearchSession(sessionId: string): Promise<MarketResearchSession> {
  const res = await fetch(`${BASE}/api/ventures/market-research/sessions/${sessionId}/retry`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<MarketResearchSession>(res)
}

export async function cloneResearchSession(sessionId: string): Promise<MarketResearchSession> {
  const res = await fetch(`${BASE}/api/ventures/market-research/sessions/${sessionId}/clone`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<MarketResearchSession>(res)
}

export async function abortResearchSession(sessionId: string): Promise<MarketResearchSession> {
  const res = await fetch(`${BASE}/api/ventures/market-research/sessions/${sessionId}/abort`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<MarketResearchSession>(res)
}


// ── Content Engine ─────────────────────────────────────────────────────────────

export interface ContentBrand {
  id: string
  slug: string
  name: string
  venture_tag: string | null
  description: string | null
  voice_profile_json: Record<string, unknown>
  theme_weights: Record<string, number>
  banned_phrases: string[]
  channel_cadence: Record<string, number>
  target_personas: { name?: string; description?: string }[]
  auto_strategy_enabled: boolean
  auto_approve_min_score: number
  voice_source_urls: string[]
  created_at: string
  updated_at: string
}

export interface ContentStrategy {
  id: string
  brand_id: string
  title: string
  period_days: number
  status: string
  pillars: string[]
  channel_cadence: Record<string, number>
  calendar: Array<{
    index?: number
    date?: string
    channel: string
    format: string
    pillar?: string
    topic?: string | null
    angle?: string | null
    hook?: string | null
  }>
  notes: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
}

export interface ContentAsset {
  id: number
  kind: "image" | "video" | "audio" | "doc" | "thumbnail" | string
  role: string | null
  channel: string | null
  drive_id: string | null
  url: string | null
  file_url: string                       // public content-engine file URL
  meta_json: Record<string, unknown>
  cost_usd: number | null
  created_at: string
}

export interface ContentItem {
  id: string
  brand_id: string
  strategy_id: string | null
  title: string | null
  format: string
  channels: string[]
  pillar: string | null
  topic: string | null
  status: string
  scheduled_for: string | null
  brief_json: Record<string, unknown>
  variants_json: Record<string, { body: string; hashtags?: string[]; subject?: string | null }>
  quality_report_json: Record<string, unknown>
  review_notes: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
  published_at: string | null
  asset_count: number
  publish_job_count: number
  assets: ContentAsset[]
}

export interface SocialAccount {
  id: string
  brand_id: string
  platform: string
  account_id: string | null
  account_name: string | null
  has_token: boolean
  expires_at: string | null
  scopes: string[]
  enabled: boolean
  created_at: string
}

export interface PublishJob {
  id: string
  item_id: string
  channel: string
  status: string
  external_post_id: string | null
  external_url: string | null
  deep_link: string | null
  error_message: string | null
  created_at: string
  published_at: string | null
}

const CE_BASE = `${BASE}/api/ventures/content-engine`

export async function fetchContentBrands(): Promise<ContentBrand[]> {
  const res = await fetch(`${CE_BASE}/brands`, { headers: getHeaders() })
  return handleResponse<ContentBrand[]>(res)
}

export async function seedEchoforgeBrand(): Promise<ContentBrand> {
  const res = await fetch(`${CE_BASE}/brands/seed-echoforge`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<ContentBrand>(res)
}

export async function patchContentBrand(
  brandId: string,
  patch: Partial<{
    name: string
    description: string | null
    auto_approve_min_score: number
    voice_source_urls: string[]
    banned_phrases: string[]
    auto_strategy_enabled: boolean
    target_personas: { name?: string; description?: string }[]
  }>,
): Promise<ContentBrand> {
  // PATCH /brands/{id} expects the full BrandIn shape minus slug; the router
  // only writes keys whose values aren't None. We pad slug+name from the
  // existing brand on the call site so the schema validation passes.
  const res = await fetch(`${CE_BASE}/brands/${brandId}`, {
    method: "PATCH",
    headers: getHeaders(),
    body: JSON.stringify(patch),
  })
  return handleResponse<ContentBrand>(res)
}

export async function regenerateBrandVoice(
  brandId: string,
  body?: { source_urls?: string[]; niche?: string; audience?: string },
): Promise<ContentBrand> {
  const res = await fetch(`${CE_BASE}/brands/${brandId}/regenerate-voice`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(body ?? {}),
  })
  return handleResponse<ContentBrand>(res)
}

export async function fetchContentStrategies(brandId?: string): Promise<ContentStrategy[]> {
  const url = new URL(`${CE_BASE}/strategies`)
  if (brandId) url.searchParams.set("brand_id", brandId)
  const res = await fetch(url.toString(), { headers: getHeaders() })
  return handleResponse<ContentStrategy[]>(res)
}

export async function createContentStrategy(body: {
  brand_id: string
  period_days?: number
  title?: string
  channel_cadence?: Record<string, number>
  user_brief?: string
  must_cover_topics?: string[]
  upcoming_events?: string[]
  tone_notes?: string
}): Promise<ContentStrategy> {
  const res = await fetch(`${CE_BASE}/strategies`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(body),
  })
  return handleResponse<ContentStrategy>(res)
}

export async function patchContentStrategy(
  strategyId: string,
  patch: Partial<{
    title: string
    notes: string
    calendar: ContentStrategy["calendar"]
    pillars: string[]
    channel_cadence: Record<string, number>
    status: string
  }>,
): Promise<ContentStrategy> {
  const res = await fetch(`${CE_BASE}/strategies/${strategyId}`, {
    method: "PATCH",
    headers: getHeaders(),
    body: JSON.stringify(patch),
  })
  return handleResponse<ContentStrategy>(res)
}

export interface CostDigest {
  brand_id: string
  brand_name: string
  window_start: string
  window_end: string
  items_published: number
  publish_events: number
  total_cost_usd: number
  cost_per_post_usd: number
}

export async function fetchCostDigest(brandId?: string, days = 7): Promise<CostDigest[]> {
  const url = new URL(`${CE_BASE}/cost-digest`)
  if (brandId) url.searchParams.set("brand_id", brandId)
  url.searchParams.set("days", String(days))
  const res = await fetch(url.toString(), { headers: getHeaders() })
  return handleResponse<CostDigest[]>(res)
}

export async function approveContentStrategy(strategyId: string): Promise<ContentStrategy> {
  const res = await fetch(`${CE_BASE}/strategies/${strategyId}/approve`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<ContentStrategy>(res)
}

export async function fetchContentItems(params?: {
  brand_id?: string
  status?: string
}): Promise<ContentItem[]> {
  const url = new URL(`${CE_BASE}/items`)
  if (params?.brand_id) url.searchParams.set("brand_id", params.brand_id)
  if (params?.status) url.searchParams.set("status_filter", params.status)
  const res = await fetch(url.toString(), { headers: getHeaders() })
  return handleResponse<ContentItem[]>(res)
}

export async function createContentItem(body: {
  brand_id: string
  strategy_id?: string
  title?: string
  format?: string
  channels?: string[]
  pillar?: string
  topic?: string
  scheduled_for?: string
}): Promise<ContentItem> {
  const res = await fetch(`${CE_BASE}/items`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(body),
  })
  return handleResponse<ContentItem>(res)
}

export async function generateContentItem(itemId: string): Promise<ContentItem> {
  const res = await fetch(`${CE_BASE}/items/${itemId}/generate`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<ContentItem>(res)
}

export async function reviewContentItem(
  itemId: string,
  action: "approve" | "revise" | "reject",
  notes?: string,
): Promise<ContentItem> {
  const res = await fetch(`${CE_BASE}/items/${itemId}/review`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ action, notes }),
  })
  return handleResponse<ContentItem>(res)
}

export async function scheduleContentItem(
  itemId: string,
  scheduledFor: string,
  channels?: string[],
): Promise<ContentItem> {
  const res = await fetch(`${CE_BASE}/items/${itemId}/schedule`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ scheduled_for: scheduledFor, channels }),
  })
  return handleResponse<ContentItem>(res)
}

export async function publishContentItemNow(itemId: string): Promise<ContentItem> {
  const res = await fetch(`${CE_BASE}/items/${itemId}/publish-now`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<ContentItem>(res)
}

export async function fetchSocialAccounts(brandId?: string): Promise<SocialAccount[]> {
  const url = new URL(`${CE_BASE}/social-accounts`)
  if (brandId) url.searchParams.set("brand_id", brandId)
  const res = await fetch(url.toString(), { headers: getHeaders() })
  return handleResponse<SocialAccount[]>(res)
}

export async function createSocialAccount(body: {
  brand_id: string
  platform: string
  account_id?: string
  account_name?: string
  access_token?: string
}): Promise<SocialAccount> {
  const res = await fetch(`${CE_BASE}/social-accounts`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(body),
  })
  return handleResponse<SocialAccount>(res)
}

export async function fetchPublishJobs(itemId?: string): Promise<PublishJob[]> {
  const url = new URL(`${CE_BASE}/publish-jobs`)
  if (itemId) url.searchParams.set("item_id", itemId)
  const res = await fetch(url.toString(), { headers: getHeaders() })
  return handleResponse<PublishJob[]>(res)
}

export interface OAuthStartResponse {
  auth_url: string
  platform: string
  brand_id: string
}

export async function startOAuth(
  platform: "linkedin" | "meta" | "youtube",
  brandId: string,
): Promise<OAuthStartResponse> {
  const url = new URL(`${CE_BASE}/oauth/${platform}/start`)
  url.searchParams.set("brand_id", brandId)
  const res = await fetch(url.toString(), {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<OAuthStartResponse>(res)
}
