import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

const API = import.meta.env.VITE_API_URL || "https://api.planbadmin.com"
const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem("api_token")}` })

const VENTURES = [
  { id: "marketing_audit",     label: "Marketing Audit",     icon: "search" },
  { id: "content_studio",      label: "Podcast Show Notes",  icon: "mic" },
  { id: "accessibility_audit", label: "Accessibility Audit", icon: "accessibility_new" },
]

const STATUS_COLORS: Record<string, string> = {
  new:            "bg-surface-container text-on-surface-variant",
  email_sent:     "bg-primary/10 text-primary",
  opened:         "bg-tertiary/10 text-tertiary",
  replied:        "bg-emerald-100 text-emerald-700",
  converted:      "bg-emerald-600 text-white",
  not_interested: "bg-surface-dim text-on-surface-variant",
  unsubscribed:   "bg-error/10 text-error",
  draft:          "bg-surface-container text-on-surface-variant",
  active:         "bg-primary/10 text-primary",
  paused:         "bg-amber-100 text-amber-700",
  completed:      "bg-emerald-100 text-emerald-700",
  pending:        "bg-amber-100 text-amber-700",
  approved:       "bg-emerald-100 text-emerald-700",
  rejected:       "bg-error/10 text-error",
  approached:     "bg-primary/10 text-primary",
  inquired:       "bg-tertiary/10 text-tertiary",
  purchased:      "bg-emerald-600 text-white",
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${STATUS_COLORS[status] ?? "bg-surface-container text-on-surface-variant"}`}>
      {status.replace(/_/g, " ")}
    </span>
  )
}

// ── API hooks ──────────────────────────────────────────────────────────────────

function useCampaigns(venture: string) {
  return useQuery({
    queryKey: ["campaigns", venture],
    queryFn: async () => {
      const r = await fetch(`${API}/api/outreach/campaigns?venture=${venture}`, { headers: authHeader() })
      if (!r.ok) throw new Error(r.statusText)
      return r.json()
    },
  })
}

function useCampaign(id: string | null) {
  return useQuery({
    queryKey: ["campaign", id],
    enabled: !!id,
    queryFn: async () => {
      const r = await fetch(`${API}/api/outreach/campaigns/${id}`, { headers: authHeader() })
      if (!r.ok) throw new Error(r.statusText)
      return r.json()
    },
  })
}

function useLeads(campaignId: string | null) {
  return useQuery({
    queryKey: ["leads", campaignId],
    enabled: !!campaignId,
    queryFn: async () => {
      const r = await fetch(`${API}/api/outreach/leads?campaign_id=${campaignId}&page_size=100`, { headers: authHeader() })
      if (!r.ok) throw new Error(r.statusText)
      return r.json()
    },
  })
}

function useStats(campaignId: string | null) {
  return useQuery({
    queryKey: ["campaign-stats", campaignId],
    enabled: !!campaignId,
    queryFn: async () => {
      const r = await fetch(`${API}/api/outreach/campaigns/${campaignId}/stats`, { headers: authHeader() })
      if (!r.ok) throw new Error(r.statusText)
      return r.json()
    },
  })
}

function useContacts(page: number, search: string, statusFilter: string) {
  return useQuery({
    queryKey: ["contacts", page, search, statusFilter],
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page), page_size: "50" })
      if (search) params.set("search", search)
      if (statusFilter) params.set("status", statusFilter)
      const r = await fetch(`${API}/api/outreach/contacts?${params}`, { headers: authHeader() })
      if (!r.ok) throw new Error(r.statusText)
      return r.json()
    },
  })
}

// ── Find Leads modal with AI-generated prompt ─────────────────────────────────

function FindLeadsModal({
  campaignId, onClose, onTriggered,
}: { campaignId: string; onClose: () => void; onTriggered: () => void }) {
  const [step, setStep] = useState<"generating" | "review" | "searching">("generating")
  const [prompt, setPrompt] = useState("")
  const [maxLeads, setMaxLeads] = useState(20)
  const [error, setError] = useState("")

  // Generate prompt on mount
  useState(() => {
    fetch(`${API}/api/outreach/campaigns/${campaignId}/generate-prompt`, {
      method: "POST",
      headers: authHeader(),
    })
      .then(r => r.json())
      .then(d => { setPrompt(d.prompt || ""); setStep("review") })
      .catch(() => { setError("Failed to generate prompt. You can write your own."); setStep("review") })
  })

  async function startSearch() {
    setStep("searching")
    try {
      await fetch(`${API}/api/outreach/campaigns/${campaignId}/find-leads`, {
        method: "POST",
        headers: { ...authHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({ max_leads: maxLeads, search_prompt: prompt }),
      })
      onTriggered()
      onClose()
    } catch {
      setError("Failed to start search.")
      setStep("review")
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/20 shadow-float w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b border-outline-variant/10 flex items-center justify-between">
          <h3 className="font-headline font-bold text-base text-on-surface">Find Leads</h3>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface">
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {step === "generating" && (
            <div className="flex items-center gap-3 text-sm text-on-surface-variant">
              <span className="material-symbols-outlined text-[20px] animate-spin">progress_activity</span>
              Generating search criteria based on your campaign…
            </div>
          )}

          {(step === "review" || step === "searching") && (
            <>
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">
                  Search Criteria Prompt
                </label>
                <p className="text-xs text-on-surface-variant mb-2">
                  This prompt guides the AI when searching and qualifying leads. Review and adjust it before searching.
                </p>
                <textarea
                  value={prompt}
                  onChange={e => setPrompt(e.target.value)}
                  rows={14}
                  className="w-full px-3 py-2.5 text-sm font-mono bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none leading-relaxed"
                />
              </div>

              <div className="flex items-center gap-4">
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Max Leads</label>
                  <input
                    type="number"
                    value={maxLeads}
                    onChange={e => setMaxLeads(Number(e.target.value))}
                    min={5} max={50}
                    className="w-24 px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface"
                  />
                </div>
              </div>

              {error && <p className="text-xs text-error">{error}</p>}
            </>
          )}
        </div>

        <div className="px-6 py-4 border-t border-outline-variant/10 flex justify-end gap-2">
          <button onClick={onClose}
            className="px-4 py-2 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg">
            Cancel
          </button>
          {(step === "review") && (
            <button onClick={startSearch} disabled={!prompt.trim()}
              className="flex items-center gap-1.5 px-4 py-2 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg disabled:opacity-50">
              <span className="material-symbols-outlined text-[14px]">search</span>
              Start Search
            </button>
          )}
          {step === "searching" && (
            <button disabled className="flex items-center gap-1.5 px-4 py-2 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg opacity-70">
              <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>
              Queuing…
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Template card ─────────────────────────────────────────────────────────────

function TemplateCard({
  template, campaignId, onSaved,
}: { template: any; campaignId: string; onSaved: () => void }) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [subject, setSubject] = useState(template.subject)
  const [body, setBody] = useState(template.body_text || "")
  const [saving, setSaving] = useState(false)
  const [approving, setApproving] = useState(false)

  async function save() {
    setSaving(true)
    await fetch(`${API}/api/outreach/templates/${template.id}`, {
      method: "PATCH",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({ subject, body_text: body }),
    })
    setSaving(false)
    setEditing(false)
    qc.invalidateQueries({ queryKey: ["campaign", campaignId] })
    onSaved()
  }

  async function setApproval(val: string) {
    setApproving(true)
    await fetch(`${API}/api/outreach/templates/${template.id}`, {
      method: "PATCH",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({ approved: val }),
    })
    setApproving(false)
    qc.invalidateQueries({ queryKey: ["campaign", campaignId] })
    onSaved()
  }

  const variantColors: Record<string, string> = {
    A: "bg-primary/10 text-primary",
    B: "bg-tertiary/10 text-tertiary",
    C: "bg-secondary-container text-on-secondary-container",
  }

  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 overflow-hidden">
      <div className="px-5 py-3 border-b border-outline-variant/10 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${variantColors[template.variant] ?? ""}`}>
            Variant {template.variant}
          </span>
          <StatusBadge status={template.approved} />
        </div>
        <div className="flex items-center gap-2 text-xs text-on-surface-variant font-label">
          <span>{template.sends} sent</span>
          <span>{template.open_rate}% open</span>
          <span>{template.reply_rate}% reply</span>
        </div>
      </div>

      <div className="p-5 space-y-3">
        {editing ? (
          <>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Subject</label>
              <input
                value={subject}
                onChange={e => setSubject(e.target.value)}
                className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface"
              />
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Body</label>
              <textarea
                value={body}
                onChange={e => setBody(e.target.value)}
                rows={10}
                className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none leading-relaxed"
              />
            </div>
            <div className="flex gap-2">
              <button onClick={save} disabled={saving}
                className="px-4 py-1.5 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg disabled:opacity-50">
                {saving ? "Saving…" : "Save"}
              </button>
              <button onClick={() => { setEditing(false); setSubject(template.subject); setBody(template.body_text || "") }}
                className="px-4 py-1.5 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg">
                Cancel
              </button>
            </div>
          </>
        ) : (
          <>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Subject</p>
              <p className="text-sm font-label text-on-surface">{template.subject}</p>
            </div>
            {template.tone_notes && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Tone & Angle</p>
                <p className="text-xs text-on-surface-variant italic">{template.tone_notes}</p>
              </div>
            )}
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Body</p>
              <pre className="text-sm font-label text-on-surface whitespace-pre-wrap leading-relaxed">{template.body_text}</pre>
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              <button onClick={() => setEditing(true)}
                className="flex items-center gap-1 px-3 py-1.5 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg hover:bg-surface-dim transition-colors">
                <span className="material-symbols-outlined text-[14px]">edit</span>Edit
              </button>
              {template.approved !== "approved" && (
                <button onClick={() => setApproval("approved")} disabled={approving}
                  className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white text-xs font-label font-semibold rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50">
                  <span className="material-symbols-outlined text-[14px]">check_circle</span>Approve
                </button>
              )}
              {template.approved !== "rejected" && (
                <button onClick={() => setApproval("rejected")} disabled={approving}
                  className="flex items-center gap-1 px-3 py-1.5 border border-error/30 text-error text-xs font-label font-semibold rounded-lg hover:bg-error-container transition-colors disabled:opacity-50">
                  <span className="material-symbols-outlined text-[14px]">cancel</span>Reject
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── Campaign detail ───────────────────────────────────────────────────────────

function CampaignDetail({ campaignId, onDeleted }: { campaignId: string; onDeleted: () => void }) {
  const qc = useQueryClient()
  const { data: campaign, isLoading } = useCampaign(campaignId)
  const { data: leadsData } = useLeads(campaignId)
  const { data: stats, refetch: refetchStats } = useStats(campaignId)
  const [activeTab, setActiveTab] = useState<"templates" | "leads" | "stats">("templates")
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [showFindLeads, setShowFindLeads] = useState(false)
  const [deleting, setDeleting] = useState(false)

  async function triggerAction(endpoint: string, body: object, actionKey: string) {
    setActionLoading(actionKey)
    try {
      const r = await fetch(`${API}/api/outreach/campaigns/${campaignId}/${endpoint}`, {
        method: "POST",
        headers: { ...authHeader(), "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      if (!r.ok) { const e = await r.json(); alert(e.detail || "Error") }
      qc.invalidateQueries({ queryKey: ["campaigns"] })
      qc.invalidateQueries({ queryKey: ["campaign", campaignId] })
      qc.invalidateQueries({ queryKey: ["leads", campaignId] })
    } finally {
      setActionLoading(null)
    }
  }

  async function deleteCampaign() {
    if (!confirm(`Delete campaign "${campaign?.name}"? This will also delete all leads, templates, and send records. This cannot be undone.`)) return
    setDeleting(true)
    await fetch(`${API}/api/outreach/campaigns/${campaignId}`, {
      method: "DELETE",
      headers: authHeader(),
    })
    qc.invalidateQueries({ queryKey: ["campaigns"] })
    onDeleted()
  }

  if (isLoading) return <div className="p-8 text-center text-sm text-on-surface-variant">Loading…</div>
  if (!campaign) return null

  const tabs = [
    { id: "templates", label: "Email Templates", icon: "mail" },
    { id: "leads",     label: `Leads (${leadsData?.total ?? 0})`, icon: "group" },
    { id: "stats",     label: "A/B Results", icon: "bar_chart" },
  ]

  return (
    <>
      {showFindLeads && (
        <FindLeadsModal
          campaignId={campaignId}
          onClose={() => setShowFindLeads(false)}
          onTriggered={() => {
            qc.invalidateQueries({ queryKey: ["leads", campaignId] })
            qc.invalidateQueries({ queryKey: ["campaign", campaignId] })
          }}
        />
      )}

      <div className="space-y-6">
        {/* Campaign header */}
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-5">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2">
                <h2 className="font-headline font-bold text-lg text-on-surface">{campaign.name}</h2>
                <StatusBadge status={campaign.status} />
              </div>
              {campaign.goal && (
                <p className="text-sm text-on-surface-variant leading-relaxed">{campaign.goal}</p>
              )}
            </div>
            <div className="flex flex-wrap items-start gap-2">
              <button
                onClick={() => setShowFindLeads(true)}
                disabled={!!actionLoading}
                className="flex items-center gap-1.5 px-3 py-2 bg-surface-container text-on-surface text-xs font-label font-semibold rounded-lg hover:bg-surface-dim disabled:opacity-50 transition-colors"
              >
                <span className="material-symbols-outlined text-[14px]">search</span>Find Leads
              </button>
              <button
                onClick={() => triggerAction("compose", {}, "compose")}
                disabled={!!actionLoading}
                className="flex items-center gap-1.5 px-3 py-2 bg-surface-container text-on-surface text-xs font-label font-semibold rounded-lg hover:bg-surface-dim disabled:opacity-50 transition-colors"
              >
                <span className="material-symbols-outlined text-[14px]">auto_awesome</span>
                {actionLoading === "compose" ? "Composing…" : "Generate Emails"}
              </button>
              <button
                onClick={() => triggerAction("send", {}, "send")}
                disabled={!!actionLoading}
                className="flex items-center gap-1.5 px-3 py-2 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                <span className="material-symbols-outlined text-[14px]">send</span>
                {actionLoading === "send" ? "Sending…" : "Send Approved"}
              </button>
              <button
                onClick={deleteCampaign}
                disabled={deleting}
                className="flex items-center gap-1.5 px-3 py-2 border border-error/30 text-error text-xs font-label font-semibold rounded-lg hover:bg-error-container disabled:opacity-50 transition-colors"
                title="Delete campaign"
              >
                <span className="material-symbols-outlined text-[14px]">delete</span>
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>

          {/* Stats bar */}
          <div className="flex items-center gap-6 mt-4 pt-4 border-t border-outline-variant/10 text-xs font-label text-on-surface-variant">
            <span><strong className="text-on-surface">{campaign.leads_count}</strong> leads</span>
            <span><strong className="text-on-surface">{campaign.total_sends}</strong> sent</span>
            <span><strong className="text-on-surface">{campaign.open_rate}%</strong> open rate</span>
            <span><strong className="text-on-surface">{campaign.reply_rate}%</strong> reply rate</span>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-surface-container-low p-1 rounded-xl w-fit">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id as any)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-label font-semibold transition-colors ${
                activeTab === t.id ? "bg-surface-container-lowest text-on-surface shadow-float" : "text-on-surface-variant hover:text-on-surface"
              }`}>
              <span className="material-symbols-outlined text-[14px]">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>

        {/* Templates tab */}
        {activeTab === "templates" && (
          <div className="space-y-4">
            {!campaign.templates?.length ? (
              <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-8 text-center">
                <span className="material-symbols-outlined text-[40px] text-on-surface-variant/30 block mb-3">mail_outline</span>
                <p className="text-sm text-on-surface-variant">No email templates yet.</p>
                <p className="text-xs text-on-surface-variant mt-1">Click "Generate Emails" to create A/B/C variants using Claude.</p>
              </div>
            ) : (
              campaign.templates.map((t: any) => (
                <TemplateCard key={t.id} template={t} campaignId={campaignId}
                  onSaved={() => qc.invalidateQueries({ queryKey: ["campaign", campaignId] })} />
              ))
            )}
          </div>
        )}

        {/* Leads tab */}
        {activeTab === "leads" && (
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 overflow-hidden">
            {!leadsData?.items?.length ? (
              <div className="p-8 text-center">
                <span className="material-symbols-outlined text-[40px] text-on-surface-variant/30 block mb-3">group</span>
                <p className="text-sm text-on-surface-variant">No leads found yet.</p>
                <p className="text-xs text-on-surface-variant mt-1">Click "Find Leads" to search Reddit and the web for potential customers.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-container-low border-b border-outline-variant/10">
                      {["Name", "Email", "Channel", "Source URL", "Company / Website", "Notes", "Status"].map(h => (
                        <th key={h} className="px-4 py-2.5 text-left text-[10px] font-label font-semibold uppercase tracking-wider text-on-surface-variant whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/10">
                    {leadsData.items.map((l: any) => (
                      <tr key={l.id} className="hover:bg-surface-container-low/40 transition-colors">
                        <td className="px-4 py-3 text-sm font-label text-on-surface whitespace-nowrap">{l.name || "—"}</td>
                        <td className="px-4 py-3 text-xs font-label text-primary">
                          {l.email ? <a href={`mailto:${l.email}`} className="hover:underline">{l.email}</a> : "—"}
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs font-label text-on-surface-variant">{l.source_channel}</span>
                        </td>
                        <td className="px-4 py-3 text-xs font-label text-on-surface-variant max-w-[160px]">
                          {l.source_url
                            ? <a href={l.source_url} target="_blank" rel="noopener noreferrer"
                                className="text-primary hover:underline truncate block"
                                title={l.source_url}>{l.source_url.replace(/^https?:\/\//, "").slice(0, 40)}</a>
                            : "—"}
                        </td>
                        <td className="px-4 py-3 text-xs font-label text-on-surface-variant max-w-[140px] truncate">
                          {l.company || l.website_url || "—"}
                        </td>
                        <td className="px-4 py-3 text-xs text-on-surface-variant max-w-[220px]">
                          <span className="line-clamp-2">{l.notes || "—"}</span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap"><StatusBadge status={l.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* A/B Stats tab */}
        {activeTab === "stats" && (
          <div className="space-y-6">
            <button onClick={() => refetchStats()}
              className="flex items-center gap-1.5 px-3 py-2 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg hover:bg-surface-dim transition-colors">
              <span className="material-symbols-outlined text-[14px]">refresh</span>Run Analysis
            </button>

            {stats && (
              <>
                {stats.variants?.length > 0 && (
                  <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 overflow-hidden">
                    <div className="px-5 py-4 border-b border-outline-variant/10">
                      <h3 className="font-headline font-bold text-sm text-on-surface">Variant Performance</h3>
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        Variants are assigned to leads based on their profile and context — not randomly.
                      </p>
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-surface-container-low border-b border-outline-variant/10">
                          {["Variant", "Subject", "Sent", "Opens", "Replies", "Open %", "Reply %"].map(h => (
                            <th key={h} className="px-4 py-2.5 text-left text-[10px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-outline-variant/10">
                        {stats.variants.map((v: any) => (
                          <tr key={v.variant} className={stats.winner === v.variant ? "bg-emerald-50" : ""}>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <span className="font-black text-on-surface">{v.variant}</span>
                                {stats.winner === v.variant && <span className="text-[10px] bg-emerald-600 text-white px-1.5 py-0.5 rounded font-bold">Winner</span>}
                              </div>
                            </td>
                            <td className="px-4 py-3 text-xs text-on-surface-variant max-w-[200px] truncate">{v.subject}</td>
                            <td className="px-4 py-3 text-sm text-on-surface">{v.sends}</td>
                            <td className="px-4 py-3 text-sm text-on-surface">{v.opens}</td>
                            <td className="px-4 py-3 text-sm text-on-surface">{v.replies}</td>
                            <td className="px-4 py-3 text-sm font-semibold text-primary">{v.open_rate}%</td>
                            <td className="px-4 py-3 text-sm font-semibold text-emerald-600">{v.reply_rate}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {stats.analysis && (
                  <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-5 space-y-4">
                    <h3 className="font-headline font-bold text-sm text-on-surface">AI Analysis</h3>
                    <p className="text-sm text-on-surface-variant leading-relaxed">{stats.analysis}</p>
                    {stats.recommendations?.length > 0 && (
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">Recommendations</p>
                        <ul className="space-y-2">
                          {stats.recommendations.map((rec: string, i: number) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-on-surface">
                              <span className="material-symbols-outlined text-[16px] text-primary mt-0.5 shrink-0">arrow_forward</span>
                              {rec}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </>
  )
}

// ── Contacts section ──────────────────────────────────────────────────────────

function ContactsSection() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [searchInput, setSearchInput] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const { data, isLoading } = useContacts(page, search, statusFilter)

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2 bg-surface-container-lowest rounded-lg border border-outline-variant/20 px-3 py-2">
          <span className="material-symbols-outlined text-[16px] text-on-surface-variant">search</span>
          <input
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") { setSearch(searchInput); setPage(1) } }}
            placeholder="Search email, name, company…"
            className="text-sm font-label text-on-surface bg-transparent outline-none w-56"
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm font-label bg-surface-container-lowest rounded-lg border border-outline-variant/20 text-on-surface"
        >
          <option value="">All statuses</option>
          <option value="approached">Approached</option>
          <option value="inquired">Inquired</option>
          <option value="purchased">Purchased</option>
          <option value="unsubscribed">Unsubscribed</option>
        </select>
        <span className="text-xs text-on-surface-variant font-label">
          {data ? `${data.total} contacts` : ""}
        </span>
      </div>

      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-on-surface-variant">Loading…</div>
        ) : !data?.items?.length ? (
          <div className="p-8 text-center">
            <span className="material-symbols-outlined text-[40px] text-on-surface-variant/30 block mb-3">contacts</span>
            <p className="text-sm text-on-surface-variant">No contacts yet.</p>
            <p className="text-xs text-on-surface-variant mt-1">Contacts are created automatically when leads are emailed.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant/10">
                  {["Name", "Email", "Company", "Status", "Ventures", "Last Activity"].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left text-[10px] font-label font-semibold uppercase tracking-wider text-on-surface-variant whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {data.items.map((c: any) => (
                  <tr key={c.id} className="hover:bg-surface-container-low/40 transition-colors">
                    <td className="px-4 py-3 text-sm font-label text-on-surface">{c.name || "—"}</td>
                    <td className="px-4 py-3 text-xs font-label text-primary">
                      <a href={`mailto:${c.email}`} className="hover:underline">{c.email}</a>
                    </td>
                    <td className="px-4 py-3 text-xs text-on-surface-variant">{c.company || "—"}</td>
                    <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                    <td className="px-4 py-3 text-xs text-on-surface-variant">
                      {(c.ventures_approached || []).join(", ").replace(/_/g, " ") || "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-on-surface-variant whitespace-nowrap">
                      {c.last_activity_at ? new Date(c.last_activity_at).toLocaleDateString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {data && data.total > 50 && (
        <div className="flex items-center justify-center gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="px-3 py-1.5 text-xs font-label text-on-surface-variant bg-surface-container rounded-lg disabled:opacity-40">Prev</button>
          <span className="text-xs text-on-surface-variant">Page {page}</span>
          <button onClick={() => setPage(p => p + 1)} disabled={page * 50 >= data.total}
            className="px-3 py-1.5 text-xs font-label text-on-surface-variant bg-surface-container rounded-lg disabled:opacity-40">Next</button>
        </div>
      )}
    </div>
  )
}

// ── Campaign sidebar card ─────────────────────────────────────────────────────

function CampaignCard({ campaign, selected, onClick }: { campaign: any; selected: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={`w-full text-left p-4 rounded-xl border transition-all ${
        selected
          ? "border-primary bg-primary/5 shadow-float"
          : "border-outline-variant/20 bg-surface-container-lowest hover:border-primary/30"
      }`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <p className="text-sm font-label font-semibold text-on-surface leading-tight">{campaign.name}</p>
        <StatusBadge status={campaign.status} />
      </div>
      <div className="flex items-center gap-4 text-xs font-label text-on-surface-variant">
        <span>{campaign.leads_count} leads</span>
        <span>{campaign.total_sends} sent</span>
        {campaign.total_sends > 0 && <span>{campaign.reply_rate}% reply</span>}
      </div>
    </button>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

type MainTab = "campaigns" | "contacts"

export default function Marketing() {
  const [mainTab, setMainTab]         = useState<MainTab>("campaigns")
  const [activeVenture, setActiveVenture] = useState(VENTURES[0].id)
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null)
  const [showNewCampaign, setShowNewCampaign] = useState(false)
  const [newName, setNewName]         = useState("")
  const [newGoal, setNewGoal]         = useState("")
  const [creating, setCreating]       = useState(false)
  const qc = useQueryClient()

  const { data: campaignsData, isLoading: campaignsLoading } = useCampaigns(activeVenture)

  async function createCampaign() {
    if (!newName.trim()) return
    setCreating(true)
    const r = await fetch(`${API}/api/outreach/campaigns`, {
      method: "POST",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({ venture: activeVenture, name: newName.trim(), goal: newGoal.trim() || null }),
    })
    if (r.ok) {
      const created = await r.json()
      setNewName("")
      setNewGoal("")
      setShowNewCampaign(false)
      qc.invalidateQueries({ queryKey: ["campaigns", activeVenture] })
      setSelectedCampaignId(created.id)
    }
    setCreating(false)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-headline font-bold text-2xl text-on-surface">Marketing</h1>
        <p className="text-sm font-body text-on-surface-variant mt-0.5">
          Cold outreach campaigns — find leads, compose A/B emails, track results
        </p>
      </div>

      {/* Main tabs: Campaigns / Contacts */}
      <div className="flex gap-1 bg-surface-container-low p-1 rounded-xl w-fit">
        {([
          { id: "campaigns", label: "Campaigns", icon: "campaign" },
          { id: "contacts",  label: "Contacts",  icon: "contacts" },
        ] as { id: MainTab; label: string; icon: string }[]).map(t => (
          <button key={t.id} onClick={() => setMainTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-label font-semibold transition-colors ${
              mainTab === t.id ? "bg-surface-container-lowest text-on-surface shadow-float" : "text-on-surface-variant hover:text-on-surface"
            }`}>
            <span className="material-symbols-outlined text-[14px]">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* Contacts tab */}
      {mainTab === "contacts" && <ContactsSection />}

      {/* Campaigns tab */}
      {mainTab === "campaigns" && (
        <>
          {/* Venture filter tabs */}
          <div className="flex gap-1 bg-surface-container-low p-1 rounded-xl w-fit">
            {VENTURES.map(v => (
              <button key={v.id}
                onClick={() => { setActiveVenture(v.id); setSelectedCampaignId(null) }}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-label font-semibold transition-colors ${
                  activeVenture === v.id
                    ? "bg-surface-container-lowest text-on-surface shadow-float"
                    : "text-on-surface-variant hover:text-on-surface"
                }`}>
                <span className="material-symbols-outlined text-[14px]">{v.icon}</span>
                {v.label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Campaign list sidebar */}
            <div className="lg:col-span-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="font-headline font-bold text-sm text-on-surface">Campaigns</h2>
                <button onClick={() => setShowNewCampaign(true)}
                  className="flex items-center gap-1 px-3 py-1.5 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg hover:opacity-90 transition-opacity">
                  <span className="material-symbols-outlined text-[14px]">add</span>New
                </button>
              </div>

              {showNewCampaign && (
                <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-4 space-y-3">
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Campaign Name</label>
                    <input
                      value={newName}
                      onChange={e => setNewName(e.target.value)}
                      placeholder="e.g. Reddit Q2 Outreach"
                      className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Campaign Goal</label>
                    <textarea
                      value={newGoal}
                      onChange={e => setNewGoal(e.target.value)}
                      placeholder="Describe the goal in detail — who we're targeting, what we want them to do, and any specific context that should inform lead search and email composition."
                      rows={4}
                      className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none leading-relaxed"
                    />
                    <p className="text-[10px] text-on-surface-variant mt-1">This is used by Claude when generating search criteria and writing emails.</p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={createCampaign} disabled={creating || !newName.trim()}
                      className="px-4 py-1.5 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg disabled:opacity-50">
                      {creating ? "Creating…" : "Create Campaign"}
                    </button>
                    <button onClick={() => setShowNewCampaign(false)}
                      className="px-4 py-1.5 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg">
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {campaignsLoading ? (
                Array(3).fill(null).map((_, i) => (
                  <div key={i} className="h-20 bg-surface-container-lowest rounded-xl animate-pulse" />
                ))
              ) : campaignsData?.items?.length ? (
                campaignsData.items.map((c: any) => (
                  <CampaignCard key={c.id} campaign={c}
                    selected={selectedCampaignId === c.id}
                    onClick={() => setSelectedCampaignId(c.id)} />
                ))
              ) : (
                <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-6 text-center">
                  <p className="text-sm text-on-surface-variant">No campaigns yet.</p>
                  <p className="text-xs text-on-surface-variant mt-1">Create one to start reaching out.</p>
                </div>
              )}
            </div>

            {/* Campaign detail */}
            <div className="lg:col-span-8">
              {selectedCampaignId ? (
                <CampaignDetail
                  campaignId={selectedCampaignId}
                  onDeleted={() => setSelectedCampaignId(null)}
                />
              ) : (
                <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-12 text-center">
                  <span className="material-symbols-outlined text-[48px] text-on-surface-variant/20 block mb-4">campaign</span>
                  <p className="text-sm text-on-surface-variant">Select a campaign to manage it</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
