import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"

const BASE = import.meta.env.VITE_API_URL || "https://api.planbadmin.com"

function getHeaders(): HeadersInit {
  const token = localStorage.getItem("api_token") ?? "test"
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: getHeaders(), ...init })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { msg = (await res.json()).detail ?? msg } catch {}
    throw new Error(msg)
  }
  return res.json()
}

// ── Types ──────────────────────────────────────────────────────────────────────

interface CampaignSummary {
  id: string
  name: string
  vendor: string
  external_id: string | null
  status: string
  daily_budget_limit: number | null
  total_budget_limit: number | null
  drive_folder_id: string | null
  creative_approved: boolean
  latest_spend: number | null
  latest_clicks: number | null
  latest_impressions: number | null
  created_at: string
}

interface CampaignDetail extends CampaignSummary {
  creative_prompt: string | null
  creative_assets: { format: string; aspect_ratio: string; url: string; file_id: string; error?: string }[] | null
  ai_insights: { summary: string; suggestions: { action: string; reason: string; priority: string }[]; budget_recommendation: string } | null
  insights_at: string | null
  metrics: { spend: number; clicks: number; impressions: number; cpa: number | null; timestamp: string }[]
}

// ── API helpers ────────────────────────────────────────────────────────────────

const api = {
  listCampaigns:     () => apiFetch<CampaignSummary[]>("/api/platform/campaigns"),
  getCampaign:       (id: string) => apiFetch<CampaignDetail>(`/api/platform/campaigns/${id}`),
  getVendors:        () => apiFetch<{ available: string[] }>("/api/platform/campaigns/vendors"),
  createCampaign:    (body: object) => apiFetch<CampaignSummary>("/api/platform/campaigns", { method: "POST", body: JSON.stringify(body) }),
  setStatus:         (id: string, status: string) => apiFetch<CampaignSummary>(`/api/platform/campaigns/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  updatePrompt:      (id: string, prompt: string) => apiFetch<CampaignDetail>(`/api/platform/campaigns/${id}/prompt`, { method: "PATCH", body: JSON.stringify({ creative_prompt: prompt }) }),
  generateCreatives: (id: string) => apiFetch<{ assets: object[]; pending_approval: boolean }>(`/api/platform/campaigns/${id}/creatives/generate`, { method: "POST", body: JSON.stringify({}) }),
  approveCreatives:  (id: string) => apiFetch<CampaignSummary>(`/api/platform/campaigns/${id}/creatives/approve`, { method: "POST", body: JSON.stringify({}) }),
  generateInsights:  (id: string) => apiFetch<{ insights: object }>(`/api/platform/campaigns/${id}/insights`, { method: "POST", body: JSON.stringify({}) }),
}

// ── Status badge ───────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  draft:   "bg-surface-variant text-on-surface-variant",
  active:  "bg-green-100 text-green-800",
  paused:  "bg-yellow-100 text-yellow-800",
  stopped: "bg-red-100 text-red-800",
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-bold capitalize ${STATUS_COLORS[status] ?? STATUS_COLORS.draft}`}>
      {status}
    </span>
  )
}

// ── Create campaign form ───────────────────────────────────────────────────────

function CreateCampaignForm({ onCreated }: { onCreated: () => void }) {
  const qc = useQueryClient()
  const { data: vendorData } = useQuery({ queryKey: ["vendors"], queryFn: api.getVendors })
  const [name, setName] = useState("")
  const [vendor, setVendor] = useState("google")
  const [dailyBudget, setDailyBudget] = useState("")
  const [totalBudget, setTotalBudget] = useState("")
  const [prompt, setPrompt] = useState("")

  const mutation = useMutation({
    mutationFn: () => api.createCampaign({
      name, vendor,
      daily_budget_limit: parseFloat(dailyBudget),
      total_budget_limit: totalBudget ? parseFloat(totalBudget) : undefined,
      creative_prompt: prompt || undefined,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["campaigns"] }); onCreated() },
  })

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-label font-bold uppercase tracking-wider text-on-surface-variant mb-1">Campaign Name</label>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. EchoForge Q3 Awareness"
            className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="block text-xs font-label font-bold uppercase tracking-wider text-on-surface-variant mb-1">Ad Platform</label>
          <select value={vendor} onChange={e => setVendor(e.target.value)}
            className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2 text-sm">
            <option value="google">Google Ads</option>
            <option value="meta">Meta (Facebook / Instagram)</option>
          </select>
          {vendorData && !vendorData.available.includes(vendor) && (
            <p className="text-xs text-yellow-600 mt-1">Credentials not configured for this vendor</p>
          )}
        </div>
        <div>
          <label className="block text-xs font-label font-bold uppercase tracking-wider text-on-surface-variant mb-1">Daily Budget ($)</label>
          <input type="number" value={dailyBudget} onChange={e => setDailyBudget(e.target.value)} placeholder="50"
            className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="block text-xs font-label font-bold uppercase tracking-wider text-on-surface-variant mb-1">
            Total Budget Limit ($) <span className="text-on-surface-variant font-normal normal-case">(optional)</span>
          </label>
          <input type="number" value={totalBudget} onChange={e => setTotalBudget(e.target.value)} placeholder="500"
            className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2 text-sm" />
        </div>
      </div>
      <div>
        <label className="block text-xs font-label font-bold uppercase tracking-wider text-on-surface-variant mb-1">
          Creative Prompt <span className="text-on-surface-variant font-normal normal-case">(optional — can be edited later in Creative Lab)</span>
        </label>
        <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={2}
          placeholder="e.g. Modern professional looking at analytics dashboard, calm blue tones, no text, no logos"
          className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2 text-sm resize-none" />
      </div>
      {mutation.isError && <p className="text-error text-sm">{mutation.error.message}</p>}
      <div className="flex justify-end gap-3">
        <button onClick={onCreated} className="px-4 py-2 text-sm text-on-surface-variant hover:text-on-surface">Cancel</button>
        <button onClick={() => mutation.mutate()} disabled={!name || !dailyBudget || mutation.isPending}
          className="btn-primary px-6 py-2 text-sm">
          {mutation.isPending ? "Creating..." : "Create Campaign"}
        </button>
      </div>
    </div>
  )
}

// ── Creative Lab tab ───────────────────────────────────────────────────────────

function CreativeLab({ campaignId, detail, onUpdated }: {
  campaignId: string
  detail: CampaignDetail
  onUpdated: () => void
}) {
  const [editingPrompt, setEditingPrompt] = useState(false)
  const [promptDraft, setPromptDraft] = useState(detail.creative_prompt ?? "")

  const promptMutation = useMutation({
    mutationFn: () => api.updatePrompt(campaignId, promptDraft),
    onSuccess: () => { setEditingPrompt(false); onUpdated() },
  })

  const generateMutation = useMutation({
    mutationFn: () => api.generateCreatives(campaignId),
    onSuccess: onUpdated,
  })

  const saveAndRegenerateMutation = useMutation({
    mutationFn: async () => {
      await api.updatePrompt(campaignId, promptDraft)
      return api.generateCreatives(campaignId)
    },
    onSuccess: () => { setEditingPrompt(false); onUpdated() },
  })

  const approveMutation = useMutation({
    mutationFn: () => api.approveCreatives(campaignId),
    onSuccess: onUpdated,
  })

  const hasAssets = !!detail.creative_assets?.length
  const isBusy = generateMutation.isPending || saveAndRegenerateMutation.isPending

  return (
    <div className="space-y-4">
      {/* Prompt editor */}
      <div className="bg-surface-container-lowest rounded-lg p-4 border border-outline-variant/20 space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-label font-bold uppercase text-on-surface-variant">Creative Prompt</p>
          {!editingPrompt && (
            <button onClick={() => { setPromptDraft(detail.creative_prompt ?? ""); setEditingPrompt(true) }}
              className="text-xs text-primary hover:underline flex items-center gap-1">
              <span className="material-symbols-outlined text-[14px]">edit</span>Edit
            </button>
          )}
        </div>
        {editingPrompt ? (
          <div className="space-y-2">
            <textarea value={promptDraft} onChange={e => setPromptDraft(e.target.value)} rows={3}
              placeholder="Describe the visual style of your ad creative — no text or logos in the image"
              className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:border-primary" />
            <div className="flex gap-2 flex-wrap">
              <button onClick={() => saveAndRegenerateMutation.mutate()}
                disabled={!promptDraft || saveAndRegenerateMutation.isPending || promptMutation.isPending}
                className="btn-primary px-3 py-1.5 text-xs flex items-center gap-1">
                <span className="material-symbols-outlined text-[14px]">refresh</span>
                {saveAndRegenerateMutation.isPending ? "Saving & Generating..." : "Save & Regenerate"}
              </button>
              <button onClick={() => promptMutation.mutate()}
                disabled={!promptDraft || promptMutation.isPending || saveAndRegenerateMutation.isPending}
                className="px-3 py-1.5 text-xs font-medium rounded-lg border border-outline-variant/40 text-on-surface hover:bg-surface-container-low">
                {promptMutation.isPending ? "Saving..." : "Save Only"}
              </button>
              <button onClick={() => setEditingPrompt(false)}
                className="px-3 py-1.5 text-xs text-on-surface-variant hover:text-on-surface">Cancel</button>
            </div>
            {(promptMutation.isError || saveAndRegenerateMutation.isError) && (
              <p className="text-error text-xs">{(promptMutation.error ?? saveAndRegenerateMutation.error)?.message}</p>
            )}
          </div>
        ) : (
          <p className="text-sm break-words">
            {detail.creative_prompt
              ? detail.creative_prompt
              : <span className="text-on-surface-variant italic">No prompt set — click Edit to add one</span>}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-3 flex-wrap">
        <button onClick={() => generateMutation.mutate()}
          disabled={isBusy || !detail.creative_prompt || editingPrompt}
          className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
          {generateMutation.isPending
            ? <><span className="material-symbols-outlined text-[16px] animate-spin">refresh</span>Generating...</>
            : <><span className="material-symbols-outlined text-[16px]">{hasAssets ? "refresh" : "auto_awesome"}</span>
               {hasAssets ? "Regenerate Assets" : "Generate Assets"}</>}
        </button>
        {detail.creative_assets && !detail.creative_approved && (
          <button onClick={() => approveMutation.mutate()} disabled={approveMutation.isPending}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-green-100 text-green-800 hover:bg-green-200">
            {approveMutation.isPending ? "Publishing..." : "Approve & Publish"}
          </button>
        )}
      </div>

      {(generateMutation.isError || approveMutation.isError) && (
        <p className="text-error text-sm">{(generateMutation.error ?? approveMutation.error)?.message}</p>
      )}

      {/* Asset list */}
      {detail.creative_assets && (
        <div className="space-y-3">
          <h3 className="text-sm font-bold flex items-center gap-2">
            Generated Assets
            {detail.creative_approved && (
              <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full font-bold">Approved</span>
            )}
          </h3>
          {detail.creative_assets.map((asset, i) => (
            <div key={i} className="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg border border-outline-variant/20">
              <div>
                <p className="font-medium text-sm">{asset.format}</p>
                <p className="text-xs text-on-surface-variant">{asset.aspect_ratio}</p>
                {asset.error && <p className="text-xs text-error mt-1">{asset.error}</p>}
              </div>
              {asset.url && (
                <a href={asset.url} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 text-primary text-xs font-medium hover:underline">
                  <span className="material-symbols-outlined text-[16px]">open_in_new</span>
                  View in Drive
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Campaign detail drawer ─────────────────────────────────────────────────────

function CampaignDrawer({ campaign, onClose }: { campaign: CampaignSummary; onClose: () => void }) {
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState<"overview" | "creatives" | "insights">("overview")

  const { data: detail, isLoading } = useQuery({
    queryKey: ["campaign", campaign.id],
    queryFn: () => api.getCampaign(campaign.id),
    refetchInterval: campaign.status === "active" ? 30000 : false,
  })

  const statusMutation = useMutation({
    mutationFn: (s: string) => api.setStatus(campaign.id, s),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] })
      qc.invalidateQueries({ queryKey: ["campaign", campaign.id] })
    },
  })

  const insightsMutation = useMutation({
    mutationFn: () => api.generateInsights(campaign.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaign", campaign.id] }),
  })

  const tabs = [
    { key: "overview",  label: "Overview" },
    { key: "creatives", label: "Creative Lab" },
    { key: "insights",  label: "AI Insights" },
  ]

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["campaigns"] })
    qc.invalidateQueries({ queryKey: ["campaign", campaign.id] })
  }

  return (
    <div className="fixed inset-0 z-50 flex" onClick={onClose}>
      <div className="flex-1 bg-black/40" />
      <div className="w-[600px] bg-surface h-full overflow-y-auto shadow-2xl flex flex-col"
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="p-6 border-b border-outline-variant/20 flex items-start justify-between gap-4 shrink-0">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <StatusBadge status={campaign.status} />
              <span className="text-xs text-on-surface-variant uppercase">{campaign.vendor}</span>
            </div>
            <h2 className="font-bold text-lg break-words">{campaign.name}</h2>
          </div>
          <button onClick={onClose} className="shrink-0 text-on-surface-variant hover:text-on-surface">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {/* Status actions */}
        <div className="px-6 py-3 border-b border-outline-variant/20 flex gap-2 shrink-0">
          {campaign.status !== "active" && campaign.status !== "stopped" && (
            <button onClick={() => statusMutation.mutate("active")} disabled={statusMutation.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-green-100 text-green-800 hover:bg-green-200">
              Resume
            </button>
          )}
          {campaign.status === "active" && (
            <button onClick={() => statusMutation.mutate("paused")} disabled={statusMutation.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-yellow-100 text-yellow-800 hover:bg-yellow-200">
              Pause
            </button>
          )}
          {campaign.status !== "stopped" && (
            <button onClick={() => statusMutation.mutate("stopped")} disabled={statusMutation.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-100 text-red-800 hover:bg-red-200">
              Stop
            </button>
          )}
          {statusMutation.isError && <span className="text-xs text-error">{statusMutation.error.message}</span>}
        </div>

        {/* Tabs */}
        <div className="px-6 pt-4 flex gap-4 border-b border-outline-variant/20 shrink-0">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setActiveTab(t.key as typeof activeTab)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === t.key
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}>
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex-1 p-6 space-y-6 overflow-y-auto">
          {isLoading && <p className="text-sm text-on-surface-variant">Loading...</p>}

          {/* ── Overview ── */}
          {activeTab === "overview" && detail && (
            <div className="space-y-6">
              <div className="card p-4 space-y-3">
                <h3 className="text-xs font-label font-bold uppercase text-on-surface-variant">Budget</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-on-surface-variant block text-xs mb-1">Daily limit</span>
                    <span className="font-bold">{campaign.daily_budget_limit ? `$${campaign.daily_budget_limit}` : "—"}</span>
                  </div>
                  <div>
                    <span className="text-on-surface-variant block text-xs mb-1">Total limit</span>
                    <span className="font-bold">{campaign.total_budget_limit ? `$${campaign.total_budget_limit}` : "—"}</span>
                  </div>
                </div>
              </div>

              <div className="card p-4 space-y-3">
                <h3 className="text-xs font-label font-bold uppercase text-on-surface-variant">Latest Metrics</h3>
                <div className="grid grid-cols-3 gap-4 text-center">
                  {[
                    { label: "Spend", value: campaign.latest_spend != null ? `$${campaign.latest_spend.toFixed(2)}` : "—" },
                    { label: "Clicks", value: campaign.latest_clicks?.toLocaleString() ?? "—" },
                    { label: "Impressions", value: campaign.latest_impressions?.toLocaleString() ?? "—" },
                  ].map(m => (
                    <div key={m.label} className="bg-surface-container-lowest rounded-lg p-3">
                      <div className="text-xl font-black">{m.value}</div>
                      <div className="text-xs text-on-surface-variant">{m.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              {detail.metrics.length > 0 && (
                <div className="card p-4">
                  <h3 className="text-xs font-label font-bold uppercase text-on-surface-variant mb-3">Metrics History</h3>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {detail.metrics.map((m, i) => (
                      <div key={i} className="flex justify-between text-xs text-on-surface-variant py-1 border-b border-outline-variant/10">
                        <span>{new Date(m.timestamp).toLocaleString()}</span>
                        <span>${m.spend.toFixed(2)} · {m.clicks} clicks · {m.impressions.toLocaleString()} impr</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Creative Lab ── */}
          {activeTab === "creatives" && detail && (
            <CreativeLab campaignId={campaign.id} detail={detail} onUpdated={invalidate} />
          )}

          {/* ── AI Insights ── */}
          {activeTab === "insights" && detail && (
            <div className="space-y-4">
              <button onClick={() => insightsMutation.mutate()} disabled={insightsMutation.isPending}
                className="btn-primary px-4 py-2 text-sm">
                {insightsMutation.isPending ? "Analysing..." : "Run AI Analysis"}
              </button>
              {insightsMutation.isError && <p className="text-error text-sm">{insightsMutation.error.message}</p>}

              {detail.ai_insights && (
                <div className="space-y-4">
                  {detail.insights_at && (
                    <p className="text-xs text-on-surface-variant">Last updated: {new Date(detail.insights_at).toLocaleString()}</p>
                  )}
                  <div className="card p-4">
                    <h3 className="text-xs font-label font-bold uppercase text-on-surface-variant mb-2">Summary</h3>
                    <p className="text-sm">{detail.ai_insights.summary}</p>
                  </div>
                  <div className="card p-4 space-y-3">
                    <h3 className="text-xs font-label font-bold uppercase text-on-surface-variant">Suggestions</h3>
                    {detail.ai_insights.suggestions?.map((s, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-surface-container-lowest rounded-lg">
                        <span className={`mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                          s.priority === "high" ? "bg-red-100 text-red-700"
                          : s.priority === "medium" ? "bg-yellow-100 text-yellow-700"
                          : "bg-surface-variant text-on-surface-variant"
                        }`}>{s.priority}</span>
                        <div>
                          <p className="font-medium text-sm">{s.action}</p>
                          <p className="text-xs text-on-surface-variant mt-0.5">{s.reason}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="card p-4">
                    <h3 className="text-xs font-label font-bold uppercase text-on-surface-variant mb-2">Budget Recommendation</h3>
                    <p className="text-sm">{detail.ai_insights.budget_recommendation}</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function CampaignManager() {
  const [showCreate, setShowCreate] = useState(false)
  const [selected, setSelected] = useState<CampaignSummary | null>(null)
  const qc = useQueryClient()

  const { data: campaigns = [], isLoading, isError, error } = useQuery({
    queryKey: ["campaigns"],
    queryFn: api.listCampaigns,
    refetchInterval: 60000,
  })

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-20">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black font-headline tracking-tight text-on-surface mb-1">Campaign Manager</h1>
          <p className="text-sm text-on-surface-variant">
            Create, monitor, and optimise paid ad campaigns across Google and Meta.
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary px-5 py-2">
          + New Campaign
        </button>
      </div>

      {showCreate && (
        <div className="card p-6">
          <h2 className="font-bold text-base mb-4">New Campaign</h2>
          <CreateCampaignForm onCreated={() => { setShowCreate(false); qc.invalidateQueries({ queryKey: ["campaigns"] }) }} />
        </div>
      )}

      {isLoading && <p className="text-sm text-on-surface-variant">Loading campaigns...</p>}
      {isError && <p className="text-sm text-error">{(error as Error).message}</p>}

      {!isLoading && campaigns.length === 0 && !showCreate && (
        <div className="card p-12 text-center text-on-surface-variant">
          <span className="material-symbols-outlined text-5xl block mb-3 opacity-30">flag</span>
          <p className="font-medium">No campaigns yet</p>
          <p className="text-sm mt-1">Create your first campaign to get started.</p>
        </div>
      )}

      {campaigns.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-outline-variant/20 text-xs font-label font-bold uppercase text-on-surface-variant">
                <th className="px-4 py-3 text-left">Campaign</th>
                <th className="px-4 py-3 text-left">Platform</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Daily Budget</th>
                <th className="px-4 py-3 text-left">Spend Today</th>
                <th className="px-4 py-3 text-left">Clicks</th>
                <th className="px-4 py-3 text-left">Impr.</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map(c => {
                const pct = c.daily_budget_limit && c.latest_spend != null
                  ? (c.latest_spend / c.daily_budget_limit) * 100 : 0
                const rowBg = pct >= 100 ? "bg-red-50" : pct >= 90 ? "bg-yellow-50" : ""
                return (
                  <tr key={c.id} onClick={() => setSelected(c)}
                    className={`border-b border-outline-variant/10 hover:bg-surface-container-lowest cursor-pointer transition-colors ${rowBg}`}>
                    <td className="px-4 py-3 font-medium">{c.name}</td>
                    <td className="px-4 py-3 capitalize text-on-surface-variant">{c.vendor}</td>
                    <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                    <td className="px-4 py-3">{c.daily_budget_limit ? `$${c.daily_budget_limit}` : "—"}</td>
                    <td className="px-4 py-3">
                      {c.latest_spend != null
                        ? <span className={pct >= 100 ? "text-red-600 font-bold" : pct >= 90 ? "text-yellow-600 font-bold" : ""}>
                            ${c.latest_spend.toFixed(2)}
                          </span>
                        : "—"}
                    </td>
                    <td className="px-4 py-3">{c.latest_clicks?.toLocaleString() ?? "—"}</td>
                    <td className="px-4 py-3">{c.latest_impressions?.toLocaleString() ?? "—"}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="px-4 py-2 text-xs text-on-surface-variant border-t border-outline-variant/10 flex gap-4">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-yellow-400 inline-block" /> ≥90% of daily budget</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-red-500 inline-block" /> Budget exhausted — auto-paused</span>
          </div>
        </div>
      )}

      {selected && (
        <CampaignDrawer campaign={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
