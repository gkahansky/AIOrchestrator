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

export async function triggerAdvisor(advisorId: string): Promise<{ status: string; proposal?: { id: string; category: string; priority: number } }> {
  const res = await fetch(`${BASE}/api/platform/strategy/advisors/${advisorId}/trigger`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<{ status: string; proposal?: { id: string; category: string; priority: number } }>(res)
}

export async function chatWithAdvisors(body: ChatRequest): Promise<ChatApiResponse> {
  const res = await fetch(`${BASE}/api/platform/strategy/chat`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(body),
  })
  return handleResponse<ChatApiResponse>(res)
}
