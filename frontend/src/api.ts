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
  RoadmapFeature,
  RoadmapItem,
  RoadmapListResponse,
  RoadmapItemCreate,
  RoadmapItemUpdate,
  ChatRequest,
  ChatApiResponse,
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
  formData.append("tier", data.tier)
  if (data.client_email) formData.append("client_email", data.client_email)
  if (data.show_name) formData.append("show_name", data.show_name)
  if (data.episode_title) formData.append("episode_title", data.episode_title)
  if (data.host_name) formData.append("host_name", data.host_name)
  if (data.guest_name) formData.append("guest_name", data.guest_name)
  if (data.special_instructions) formData.append("special_instructions", data.special_instructions)
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

export interface MarketResearchDetail extends MarketResearchSession {
  optimized_prompts: Record<string, string> | null
  research_results: Record<string, string> | null
  merged_report: string | null
  critic_feedback: string | null
  final_report: string | null
  error: string | null
}

export async function fetchAvailableLlms(): Promise<{ available: string[] }> {
  const res = await fetch(`${BASE}/api/ventures/market-research/available-llms`, { headers: getHeaders() })
  return handleResponse<{ available: string[] }>(res)
}

export async function createMarketResearchSession(body: {
  topic: string
  selected_llms?: string[]
  critic_llm?: string
  client_email?: string
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
