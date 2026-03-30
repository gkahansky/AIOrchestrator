import type {
  Job,
  JobListResponse,
  DashboardStats,
  FinanceData,
  HealthData,
  AuditOrderRequest,
  PodcastOrderRequest,
  OrderResponse,
  Settings,
  ApiKeyTestResult,
} from "./types"

const BASE = import.meta.env.VITE_API_URL || "https://api.echoforge.biz"

function getHeaders(): HeadersInit {
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
      message = body.detail ?? body.message ?? message
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

export async function createPodcastOrder(data: PodcastOrderRequest): Promise<OrderResponse> {
  const res = await fetch(`${BASE}/api/ventures/content-studio/orders`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(data),
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

export async function fetchSettings(type: string): Promise<Settings> {
  const res = await fetch(`${BASE}/api/platform/settings/${type}`, { headers: getHeaders() })
  return handleResponse<Settings>(res)
}

export async function testApiKey(service: string): Promise<ApiKeyTestResult> {
  const res = await fetch(`${BASE}/api/platform/settings/keys/${service}/test`, {
    method: "POST",
    headers: getHeaders(),
  })
  return handleResponse<ApiKeyTestResult>(res)
}

export async function updateApiKey(service: string, value: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE}/api/platform/settings/keys/${service}`, {
    method: "PATCH",
    headers: getHeaders(),
    body: JSON.stringify({ value }),
  })
  return handleResponse<{ message: string }>(res)
}
