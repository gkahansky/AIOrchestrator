import { useState, useEffect, useRef } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import CampaignManager from "./CampaignManager"

const API = import.meta.env.VITE_API_URL || "https://api.planbadmin.com"
const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem("api_token")}` })

// ── Constants ────────────────────────────────────────────────────────────────────────

const PRODUCTS = [
  { id: "market_research",     label: "Market Research",     icon: "analytics" },
  { id: "marketing_audit",     label: "Marketing Audit",     icon: "search" },
  { id: "accessibility_audit", label: "Accessibility Audit", icon: "accessibility_new" },
  { id: "security_audit",      label: "Security Audit",      icon: "security" },
  { id: "other",               label: "Other",               icon: "category" },
]

const OUTREACH_PLATFORMS = [
  { id: "email",     label: "Email",     icon: "mail" },
  { id: "fiverr",    label: "Fiverr",    icon: "work" },
  { id: "reddit",    label: "Reddit",    icon: "forum" },
  { id: "linkedin",  label: "LinkedIn",  icon: "person_search" },
  { id: "facebook",  label: "Facebook",  icon: "groups" },
  { id: "instagram", label: "Instagram", icon: "photo_camera" },
]

const SOURCE_PLATFORMS = [
  { id: "reddit",       label: "Reddit",        icon: "forum" },
  { id: "google",       label: "Google",         icon: "search" },
  { id: "linkedin",     label: "LinkedIn",       icon: "person_search" },
  { id: "facebook",     label: "Facebook",       icon: "groups" },
  { id: "hackernews",   label: "Hacker News",    icon: "code" },
  { id: "indiehackers", label: "IndieHackers",   icon: "rocket_launch" },
  { id: "fiverr",       label: "Fiverr",         icon: "work" },
  { id: "listennotes",  label: "Listen Notes",   icon: "headphones" },
  { id: "youtube",      label: "YouTube",        icon: "play_circle" },
  { id: "instagram",    label: "Instagram",      icon: "photo_camera" },
]

const SEARCH_INTERVALS = [
  { value: null,  label: "Manual only" },
  { value: 6,     label: "Every 6 hours" },
  { value: 24,    label: "Daily" },
  { value: 168,   label: "Weekly" },
]

type SourceObj = {
  id?: string
  platform: string
  name: string
  keywords: string[]
  config: Record<string, any>
  enabled: boolean
}

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
  pending_review: "bg-amber-100 text-amber-700",
  approved:       "bg-emerald-100 text-emerald-700",
  rejected:       "bg-error/10 text-error",
  awaiting_send:  "bg-sky-100 text-sky-700",
  sent:           "bg-primary/10 text-primary",
  test_sent:      "bg-violet-100 text-violet-700",
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

function PlatformBadge({ platform, small }: { platform: string; small?: boolean }) {
  const p = OUTREACH_PLATFORMS.find(x => x.id === platform)
    ?? SOURCE_PLATFORMS.find(x => x.id === platform)
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container text-on-surface-variant font-bold uppercase tracking-wider ${small ? "text-[10px]" : "text-[11px]"}`}>
      <span className={`material-symbols-outlined ${small ? "text-[11px]" : "text-[13px]"}`}>{p?.icon ?? "send"}</span>
      {p?.label ?? platform}
    </span>
  )
}

// ── API hooks ───────────────────────────────────────────────────────────────────────

function useCampaigns() {
  return useQuery({
    queryKey: ["campaigns"],
    queryFn: async () => {
      const r = await fetch(`${API}/api/outreach/campaigns`, { headers: authHeader() })
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

function useLeads(campaignId: string | null, polling = false) {
  return useQuery({
    queryKey: ["leads", campaignId],
    enabled: !!campaignId,
    refetchInterval: polling ? 3000 : false,
    queryFn: async () => {
      const r = await fetch(`${API}/api/outreach/leads?campaign_id=${campaignId}&page_size=100`, { headers: authHeader() })
      if (!r.ok) throw new Error(r.statusText)
      return r.json()
    },
  })
}

function useDrafts(campaignId: string | null, statusFilter?: string) {
  return useQuery({
    queryKey: ["drafts", campaignId, statusFilter],
    enabled: !!campaignId,
    queryFn: async () => {
      const params = new URLSearchParams()
      if (statusFilter) params.set("status", statusFilter)
      const r = await fetch(`${API}/api/outreach/campaigns/${campaignId}/drafts?${params}`, { headers: authHeader() })
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

// ── Persona editor ─────────────────────────────────────────────────────────────────────

function PersonaEditor({ personas, onChange }: {
  personas: { name: string; description: string }[]
  onChange: (p: { name: string; description: string }[]) => void
}) {
  function add() {
    if (personas.length >= 5) return
    onChange([...personas, { name: "", description: "" }])
  }
  function update(i: number, field: "name" | "description", val: string) {
    const next = personas.map((p, idx) => idx === i ? { ...p, [field]: val } : p)
    onChange(next)
  }
  function remove(i: number) {
    onChange(personas.filter((_, idx) => idx !== i))
  }

  return (
    <div className="space-y-3">
      {personas.map((p, i) => (
        <div key={i} className="bg-surface-container-low rounded-lg border border-outline-variant/20 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <input
              value={p.name}
              onChange={e => update(i, "name", e.target.value)}
              placeholder={`Persona ${i + 1} name (e.g. "Solo podcaster")`}
              className="flex-1 px-3 py-1.5 text-sm font-label bg-surface-container-lowest rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface"
            />
            <button onClick={() => remove(i)} className="text-on-surface-variant hover:text-error transition-colors">
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>
          <textarea
            value={p.description}
            onChange={e => update(i, "description", e.target.value)}
            placeholder="Describe this persona — their role, pain points, what they're usually trying to solve…"
            rows={2}
            className="w-full px-3 py-1.5 text-sm font-label bg-surface-container-lowest rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none"
          />
        </div>
      ))}
      {personas.length < 5 && (
        <button onClick={add}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-dashed border-outline-variant/40 text-on-surface-variant hover:border-primary/30 hover:text-on-surface rounded-lg text-xs font-label font-semibold transition-colors">
          <span className="material-symbols-outlined text-[14px]">add</span>Add Persona
        </button>
      )}
    </div>
  )
}

// ── Persona library (reusable, linked to campaigns) ─────────────────────────────────────

function PersonaLibrary({ campaignId, venture, onOpenPersona }: { campaignId: string; venture: string; onOpenPersona?: (id: string) => void }) {
  const [library, setLibrary] = useState<any[]>([])
  const [linkedIds, setLinkedIds] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [newName, setNewName] = useState("")
  const [newDesc, setNewDesc] = useState("")

  async function load() {
    setLoading(true)
    const [lib, linked] = await Promise.all([
      fetch(`${API}/api/outreach/personas?venture=${venture}`, { headers: authHeader() }).then(r => r.json()),
      fetch(`${API}/api/outreach/campaigns/${campaignId}/personas`, { headers: authHeader() }).then(r => r.json()),
    ])
    setLibrary(lib.items || [])
    setLinkedIds(new Set((linked.items || []).map((p: any) => p.id)))
    setLoading(false)
  }
  useEffect(() => { load() }, [campaignId, venture])

  async function saveLinks(ids: Set<string>) {
    setSaving(true)
    await fetch(`${API}/api/outreach/campaigns/${campaignId}/personas`, {
      method: "PUT", headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({ persona_ids: [...ids] }),
    })
    setSaving(false)
  }
  async function toggle(id: string) {
    const next = new Set(linkedIds)
    next.has(id) ? next.delete(id) : next.add(id)
    setLinkedIds(next)
    await saveLinks(next)
  }
  async function createPersona() {
    if (!newName.trim()) return
    setSaving(true)
    await fetch(`${API}/api/outreach/personas`, {
      method: "POST", headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName.trim(), description: newDesc.trim(), venture }),
    })
    setNewName(""); setNewDesc(""); setSaving(false)
    await load()
  }
  async function editPersona(p: any) {
    const name = window.prompt("Persona name", p.name)
    if (name === null) return
    const description = window.prompt("Description (applies to every campaign using this persona)", p.description)
    if (description === null) return
    await fetch(`${API}/api/outreach/personas/${p.id}`, {
      method: "PATCH", headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    })
    await load()
  }
  async function deletePersona(p: any) {
    if (!window.confirm(`Delete persona "${p.name}"? It will be unlinked from all campaigns.`)) return
    const r = await fetch(`${API}/api/outreach/personas/${p.id}?force=true`, {
      method: "DELETE", headers: authHeader(),
    })
    if (r.ok || r.status === 204) await load()
  }

  if (loading) return <p className="text-sm text-on-surface-variant">Loading personas…</p>

  return (
    <div className="space-y-4">
      <p className="text-xs text-on-surface-variant">
        Personas are reusable across campaigns. Check the ones this campaign targets.
        Editing a persona's text updates it everywhere it's linked.
      </p>

      <div className="space-y-2">
        {library.map(p => (
          <div key={p.id} className="flex items-start gap-3 bg-surface-container-low rounded-lg border border-outline-variant/20 p-3">
            <input type="checkbox" checked={linkedIds.has(p.id)} onChange={() => toggle(p.id)} disabled={saving}
              className="mt-1 accent-primary" />
            <div className="flex-1 min-w-0">
              {onOpenPersona ? (
                <button onClick={() => onOpenPersona(p.id)}
                  className="text-sm font-label font-semibold text-primary hover:underline text-left">{p.name}</button>
              ) : (
                <p className="text-sm font-label font-semibold text-on-surface">{p.name}</p>
              )}
              <p className="text-xs text-on-surface-variant leading-relaxed line-clamp-3">{p.description}</p>
            </div>
            <button onClick={() => editPersona(p)} className="text-on-surface-variant hover:text-primary transition-colors">
              <span className="material-symbols-outlined text-[16px]">edit</span>
            </button>
            <button onClick={() => deletePersona(p)} className="text-on-surface-variant hover:text-error transition-colors">
              <span className="material-symbols-outlined text-[16px]">delete</span>
            </button>
          </div>
        ))}
        {!library.length && <p className="text-sm text-on-surface-variant">No personas yet — create one below.</p>}
      </div>

      <div className="bg-surface-container-low rounded-lg border border-outline-variant/20 p-3 space-y-2">
        <input value={newName} onChange={e => setNewName(e.target.value)} placeholder='New persona name (e.g. "Solo podcaster")'
          className="w-full px-3 py-1.5 text-sm font-label bg-surface-container-lowest rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
        <textarea value={newDesc} onChange={e => setNewDesc(e.target.value)} rows={2}
          placeholder="Describe this persona — their role, pain points, what they're usually trying to solve…"
          className="w-full px-3 py-1.5 text-sm font-label bg-surface-container-lowest rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none" />
        <button onClick={createPersona} disabled={saving || !newName.trim()}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-on-primary rounded-lg text-xs font-label font-semibold disabled:opacity-50 transition-colors">
          <span className="material-symbols-outlined text-[14px]">add</span>Add to library
        </button>
      </div>
    </div>
  )
}

// ── Source row ─────────────────────────────────────────────────────────────────────────

function SourceRow({ source, onSave, onDelete }: {
  source: any
  onSave: (id: string, patch: any) => void
  onDelete: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [keywords, setKeywords] = useState((source.keywords || []).join(", "))
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    await onSave(source.id, {
      keywords: keywords.split(",").map((k: string) => k.trim()).filter(Boolean),
    })
    setSaving(false)
    setExpanded(false)
  }

  return (
    <div className="bg-surface-container-lowest rounded-lg border border-outline-variant/20 overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2.5">
        <PlatformBadge platform={source.platform} small />
        <span className="flex-1 text-sm font-label text-on-surface">{source.name}</span>
        <span className="text-xs text-on-surface-variant">{(source.keywords || []).length} keywords</span>
        <button
          onClick={() => onSave(source.id, { enabled: !source.enabled })}
          className={`text-xs font-label font-semibold px-2 py-0.5 rounded transition-colors ${source.enabled ? "bg-emerald-100 text-emerald-700" : "bg-surface-dim text-on-surface-variant"}`}
        >
          {source.enabled ? "ON" : "OFF"}
        </button>
        <button onClick={() => setExpanded(e => !e)} className="text-on-surface-variant hover:text-on-surface">
          <span className="material-symbols-outlined text-[18px]">{expanded ? "expand_less" : "expand_more"}</span>
        </button>
        <button onClick={() => onDelete(source.id)} className="text-on-surface-variant hover:text-error transition-colors">
          <span className="material-symbols-outlined text-[16px]">delete</span>
        </button>
      </div>

      {expanded && (
        <div className="px-4 pb-3 border-t border-outline-variant/10 pt-3 space-y-2">
          <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">
            Keywords / Queries (comma-separated)
          </label>
          <textarea
            value={keywords}
            onChange={e => setKeywords(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none"
          />
          {source.platform === "reddit" && (
            <p className="text-[10px] text-on-surface-variant">
              Subreddits: {(source.config?.subreddits || []).join(", ") || "none configured"}
            </p>
          )}
          {source.platform === "facebook" && (
            <p className="text-[10px] text-on-surface-variant">
              Groups: {(source.config?.group_urls || []).join(", ") || "generic search"}
            </p>
          )}
          <div className="flex gap-2 pt-1">
            <button onClick={save} disabled={saving}
              className="px-3 py-1.5 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg disabled:opacity-50">
              {saving ? "Saving…" : "Save"}
            </button>
            <button onClick={() => setExpanded(false)}
              className="px-3 py-1.5 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Add source modal ─────────────────────────────────────────────────────────────────────

function AddSourceModal({ campaignId, onClose, onAdded, onSubmit }: {
  campaignId?: string
  onClose: () => void
  onAdded?: () => void
  onSubmit?: (source: SourceObj) => void
}) {
  const [platform, setPlatform] = useState("reddit")
  const [name, setName] = useState("")
  const [keywords, setKeywords] = useState("")
  const [groupUrls, setGroupUrls] = useState("")
  const [subreddits, setSubreddits] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const platformInfo = SOURCE_PLATFORMS.find(p => p.id === platform)

  async function save() {
    if (!name.trim() || !keywords.trim()) { setError("Name and keywords are required."); return }
    const config: Record<string, any> = {}
    if (platform === "reddit" && subreddits.trim()) {
      config.subreddits = subreddits.split(",").map(s => s.trim()).filter(Boolean)
    }
    if (platform === "facebook" && groupUrls.trim()) {
      config.group_urls = groupUrls.split(",").map(u => u.trim()).filter(Boolean)
    }
    const source: SourceObj = {
      platform, name: name.trim(),
      keywords: keywords.split(",").map(k => k.trim()).filter(Boolean),
      config, enabled: true,
    }
    // Collect mode (new campaign — no id yet): hand the source to the parent
    if (onSubmit) { onSubmit(source); onClose(); return }
    setSaving(true)
    const r = await fetch(`${API}/api/outreach/campaigns/${campaignId}/sources`, {
      method: "POST",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify(source),
    })
    setSaving(false)
    if (r.ok) { onAdded?.(); onClose() } else { setError("Failed to add source.") }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/20 shadow-float w-full max-w-lg">
        <div className="px-6 py-4 border-b border-outline-variant/10 flex items-center justify-between">
          <h3 className="font-headline font-bold text-base text-on-surface">Add Search Source</h3>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface">
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Platform</label>
            <div className="flex flex-wrap gap-2">
              {SOURCE_PLATFORMS.map(p => (
                <button key={p.id} onClick={() => setPlatform(p.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-label font-semibold border transition-colors ${platform === p.id ? "border-primary bg-primary/5 text-primary" : "border-outline-variant/20 text-on-surface-variant hover:border-primary/30"}`}>
                  <span className="material-symbols-outlined text-[13px]">{p.icon}</span>
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Source Name</label>
            <input value={name} onChange={e => setName(e.target.value)}
              placeholder={platform === "reddit" ? "e.g. r/smallbusiness" : platform === "facebook" ? "e.g. SaaS Founders Group" : `${platformInfo?.label} search`}
              className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Keywords (comma-separated)</label>
            <textarea value={keywords} onChange={e => setKeywords(e.target.value)}
              placeholder="website not converting, seo help, marketing strategy"
              rows={3}
              className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none" />
          </div>

          {platform === "reddit" && (
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Subreddits (comma-separated)</label>
              <input value={subreddits} onChange={e => setSubreddits(e.target.value)}
                placeholder="entrepreneur, smallbusiness, startups"
                className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
            </div>
          )}

          {platform === "facebook" && (
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Group URLs (comma-separated)</label>
              <input value={groupUrls} onChange={e => setGroupUrls(e.target.value)}
                placeholder="https://www.facebook.com/groups/smallbizowners"
                className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
              <p className="text-[10px] text-on-surface-variant mt-1">Requires APIFY_API_TOKEN. Falls back to Google signals if not set.</p>
            </div>
          )}

          {error && <p className="text-xs text-error">{error}</p>}
        </div>
        <div className="px-6 py-4 border-t border-outline-variant/10 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg">Cancel</button>
          <button onClick={save} disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg disabled:opacity-50">
            {saving ? "Adding…" : "Add Source"}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Find Leads modal ─────────────────────────────────────────────────────────────────────

function FindLeadsModal({ campaignId, onClose, onTriggered }: {
  campaignId: string; onClose: () => void; onTriggered: () => void
}) {
  const [step, setStep] = useState<"generating" | "review" | "searching">("generating")
  const [prompt, setPrompt] = useState("")
  const [maxLeads, setMaxLeads] = useState(20)
  const [error, setError] = useState("")

  useEffect(() => {
    fetch(`${API}/api/outreach/campaigns/${campaignId}/generate-prompt`, {
      method: "POST", headers: authHeader(),
    })
      .then(r => r.json())
      .then(d => { setPrompt(d.prompt || ""); setStep("review") })
      .catch(() => { setError("Could not auto-generate. Write your own criteria."); setStep("review") })
  }, [campaignId])

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
    } catch { setError("Failed to start search."); setStep("review") }
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
              Generating search criteria from your personas and campaign context…
            </div>
          )}
          {(step === "review" || step === "searching") && (
            <>
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">
                  AI-Generated Search Criteria
                </label>
                <p className="text-xs text-on-surface-variant mb-2">
                  Claude generated this from your personas and campaign goal. Review and adjust before searching.
                </p>
                <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={14}
                  className="w-full px-3 py-2.5 text-sm font-mono bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none leading-relaxed" />
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Max Leads</label>
                <input type="number" value={maxLeads} onChange={e => setMaxLeads(Number(e.target.value))} min={5} max={50}
                  className="w-24 px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
              </div>
              {error && <p className="text-xs text-error">{error}</p>}
            </>
          )}
        </div>
        <div className="px-6 py-4 border-t border-outline-variant/10 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg">Cancel</button>
          {step === "review" && (
            <button onClick={startSearch} disabled={!prompt.trim()}
              className="flex items-center gap-1.5 px-4 py-2 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg disabled:opacity-50">
              <span className="material-symbols-outlined text-[14px]">search</span>Start Search
            </button>
          )}
          {step === "searching" && (
            <button disabled className="flex items-center gap-1.5 px-4 py-2 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg opacity-70">
              <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>Queuing…
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Draft card ───────────────────────────────────────────────────────────────────────────

function DraftCard({ draft, onUpdate }: { draft: any; onUpdate: () => void }) {
  const [editing, setEditing] = useState(false)
  const [body, setBody] = useState(draft.message_body || "")
  const [subject, setSubject] = useState(draft.subject || "")
  const [saving, setSaving] = useState(false)

  const lead = draft.lead || {}
  const isEmail = draft.subject !== null && draft.subject !== undefined

  async function patch(patch: any) {
    setSaving(true)
    await fetch(`${API}/api/outreach/drafts/${draft.id}`, {
      method: "PATCH",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    })
    setSaving(false)
    onUpdate()
  }

  async function saveEdit() {
    await patch({ subject: isEmail ? subject : undefined, message_body: body })
    setEditing(false)
  }

  async function sendNow() {
    setSaving(true)
    await fetch(`${API}/api/outreach/campaigns/${draft.campaign_id}/drafts/${draft.id}/send`, {
      method: "POST", headers: authHeader(),
    })
    setSaving(false)
    onUpdate()
  }

  async function confirmSent() {
    setSaving(true)
    await fetch(`${API}/api/outreach/drafts/${draft.id}/confirm-sent`, {
      method: "POST", headers: authHeader(),
    })
    setSaving(false)
    onUpdate()
  }

  function copyMessage() {
    const text = (isEmail && draft.subject ? draft.subject + "\n\n" : "") + (draft.message_body || "")
    navigator.clipboard?.writeText(text)
  }

  const statusColor = draft.status === "approved" ? "border-emerald-300 bg-emerald-50/50"
    : draft.status === "rejected" ? "border-error/20 bg-error/5"
    : draft.status === "awaiting_send" ? "border-sky-300 bg-sky-50/50"
    : "border-outline-variant/20"

  return (
    <div className={`bg-surface-container-lowest rounded-xl border overflow-hidden ${statusColor}`}>
      {/* Lead context header */}
      <div className="px-5 py-3 border-b border-outline-variant/10 bg-surface-container-low/60">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-label font-semibold text-on-surface">
                {lead.name || lead.platform_username || "Unknown"}
              </span>
              {lead.source_channel && <PlatformBadge platform={lead.source_channel} small />}
              {lead.matched_persona && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-tertiary/10 text-tertiary font-bold uppercase">
                  {lead.matched_persona}
                </span>
              )}
              <StatusBadge status={draft.status} />
            </div>
            {lead.company && <p className="text-xs text-on-surface-variant">{lead.company}</p>}
            {lead.source_url && (
              <a href={lead.source_url} target="_blank" rel="noopener noreferrer"
                className="text-[11px] text-primary hover:underline truncate block max-w-xs">
                {lead.source_url.replace(/^https?:\/\//, "").slice(0, 60)}
              </a>
            )}
          </div>
        </div>

        {/* Their post context */}
        {lead.context && (
          <div className="mt-2 px-3 py-2 bg-surface-container rounded-lg">
            <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Their post</p>
            <p className="text-xs text-on-surface-variant leading-relaxed line-clamp-3">{lead.context}</p>
          </div>
        )}
      </div>

      {/* AI-written message */}
      <div className="p-5">
        {editing ? (
          <div className="space-y-3">
            {isEmail && (
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Subject</label>
                <input value={subject} onChange={e => setSubject(e.target.value)}
                  className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
              </div>
            )}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Message</label>
              <textarea value={body} onChange={e => setBody(e.target.value)} rows={8}
                className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none leading-relaxed" />
            </div>
            <div className="flex gap-2">
              <button onClick={saveEdit} disabled={saving}
                className="px-4 py-1.5 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg disabled:opacity-50">
                {saving ? "Saving…" : "Save"}
              </button>
              <button onClick={() => { setEditing(false); setBody(draft.message_body); setSubject(draft.subject || "") }}
                className="px-4 py-1.5 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {isEmail && draft.subject && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-0.5">Subject</p>
                <p className="text-sm font-label text-on-surface">{draft.subject}</p>
              </div>
            )}
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Message</p>
              <pre className="text-sm font-label text-on-surface whitespace-pre-wrap leading-relaxed">{draft.message_body}</pre>
            </div>
            {draft.status === "pending_review" && (
              <div className="flex flex-wrap gap-2 pt-1">
                <button onClick={() => setEditing(true)}
                  className="flex items-center gap-1 px-3 py-1.5 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg hover:bg-surface-dim transition-colors">
                  <span className="material-symbols-outlined text-[13px]">edit</span>Edit
                </button>
                <button onClick={() => patch({ status: "approved" })} disabled={saving}
                  className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white text-xs font-label font-semibold rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50">
                  <span className="material-symbols-outlined text-[13px]">check_circle</span>Approve
                </button>
                <button onClick={() => patch({ status: "rejected" })} disabled={saving}
                  className="flex items-center gap-1 px-3 py-1.5 border border-error/30 text-error text-xs font-label font-semibold rounded-lg hover:bg-error-container transition-colors disabled:opacity-50">
                  <span className="material-symbols-outlined text-[13px]">cancel</span>Reject
                </button>
              </div>
            )}
            {draft.status === "approved" && (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <button onClick={sendNow} disabled={saving}
                  className="flex items-center gap-1 px-3 py-1.5 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50">
                  <span className="material-symbols-outlined text-[13px]">send</span>
                  {saving ? "Sending…" : "Send now"}
                </button>
                <span className="flex items-center gap-1 text-xs text-emerald-700">
                  <span className="material-symbols-outlined text-[14px]">check_circle</span>
                  Approved
                </span>
              </div>
            )}
            {draft.status === "awaiting_send" && (
              <div className="space-y-2 pt-1">
                <p className="text-xs text-sky-700 flex items-center gap-1">
                  <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                  Send this manually on {draft.send_platform || "the platform"}, then mark it sent.
                </p>
                <div className="flex flex-wrap gap-2">
                  {draft.send_deep_link && (
                    <a href={draft.send_deep_link} target="_blank" rel="noopener noreferrer"
                      className="flex items-center gap-1 px-3 py-1.5 bg-sky-600 text-white text-xs font-label font-semibold rounded-lg hover:bg-sky-700 transition-colors">
                      <span className="material-symbols-outlined text-[13px]">open_in_new</span>
                      Open in {draft.send_platform || "app"}
                    </a>
                  )}
                  <button onClick={copyMessage}
                    className="flex items-center gap-1 px-3 py-1.5 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg hover:bg-surface-dim transition-colors">
                    <span className="material-symbols-outlined text-[13px]">content_copy</span>Copy message
                  </button>
                  <button onClick={confirmSent} disabled={saving}
                    className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white text-xs font-label font-semibold rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50">
                    <span className="material-symbols-outlined text-[13px]">check_circle</span>
                    {saving ? "Saving…" : "Mark as sent"}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Campaign detail ────────────────────────────────────────────────────────────────────────

const SEARCH_TIMEOUT_MS = 120_000

function CampaignDetail({ campaignId, onDeleted, onCloned, onEdit, onOpenPersona }: { campaignId: string; onDeleted: () => void; onCloned: (id: string) => void; onEdit?: () => void; onOpenPersona?: (id: string) => void }) {
  const qc = useQueryClient()
  const { data: campaign, isLoading } = useCampaign(campaignId)
  const [searchingLeads, setSearchingLeads] = useState(false)
  const { data: leadsData } = useLeads(campaignId, searchingLeads)
  const [activeTab, setActiveTab] = useState<"leads" | "drafts" | "sources" | "personas">("leads")
  const [draftStatusFilter, setDraftStatusFilter] = useState("pending_review")
  const { data: draftsData, refetch: refetchDrafts } = useDrafts(campaignId, draftStatusFilter)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [showFindLeads, setShowFindLeads] = useState(false)
  const [showAddSource, setShowAddSource] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [cloning, setCloning] = useState(false)
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const prevLeadCountRef = useRef<number>(0)
  const stableCountSinceRef = useRef<number | null>(null)

  useEffect(() => {
    if (!searchingLeads) return
    const currentCount = leadsData?.total ?? 0
    if (currentCount !== prevLeadCountRef.current) {
      prevLeadCountRef.current = currentCount
      stableCountSinceRef.current = Date.now()
    } else if (stableCountSinceRef.current && Date.now() - stableCountSinceRef.current > 12_000 && currentCount > 0) {
      setSearchingLeads(false)
    }
  }, [leadsData?.total, searchingLeads])

  function startSearchPolling() {
    setSearchingLeads(true)
    prevLeadCountRef.current = leadsData?.total ?? 0
    stableCountSinceRef.current = null
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current)
    searchTimeoutRef.current = setTimeout(() => setSearchingLeads(false), SEARCH_TIMEOUT_MS)
  }

  useEffect(() => () => { if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current) }, [])

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
      qc.invalidateQueries({ queryKey: ["drafts", campaignId] })

    } finally { setActionLoading(null) }
  }

  async function deleteCampaign() {
    if (!confirm(`Delete campaign "${campaign?.name}"? All leads, sources, and drafts will be deleted. This cannot be undone.`)) return
    setDeleting(true)
    await fetch(`${API}/api/outreach/campaigns/${campaignId}`, { method: "DELETE", headers: authHeader() })
    qc.invalidateQueries({ queryKey: ["campaigns"] })
    onDeleted()
  }

  async function cloneCampaign() {
    setCloning(true)
    try {
      const r = await fetch(`${API}/api/outreach/campaigns/${campaignId}/clone`, {
        method: "POST",
        headers: authHeader(),
      })
      if (!r.ok) { const e = await r.json(); alert(e.detail || "Failed to clone campaign"); return }
      const cloned = await r.json()
      qc.invalidateQueries({ queryKey: ["campaigns"] })
      onCloned(cloned.id)
    } finally {
      setCloning(false)
    }
  }

  async function patchCampaign(patch: any) {
    await fetch(`${API}/api/outreach/campaigns/${campaignId}`, {
      method: "PATCH",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    })
    qc.invalidateQueries({ queryKey: ["campaign", campaignId] })
  }

  async function patchSchedule(intervalHours: number | null) {
    await fetch(`${API}/api/outreach/campaigns/${campaignId}/schedule`, {
      method: "PATCH",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({
        auto_search_enabled: intervalHours !== null,
        search_interval_hours: intervalHours,
      }),
    })
    qc.invalidateQueries({ queryKey: ["campaign", campaignId] })
    qc.invalidateQueries({ queryKey: ["campaigns"] })
  }

  async function patchSource(id: string, patch: any) {
    await fetch(`${API}/api/outreach/sources/${id}`, {
      method: "PATCH",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    })
    qc.invalidateQueries({ queryKey: ["campaign", campaignId] })
  }

  async function resetSources() {
    if (campaign?.venture === "other") {
      alert("No default available for 'Other' product type.")
      return
    }
    const productLabel = PRODUCTS.find(p => p.id === campaign?.venture)?.label ?? campaign?.venture
    if (!confirm(`Replace all sources with the default ${productLabel} sources? This cannot be undone.`)) return
    const r = await fetch(`${API}/api/outreach/campaigns/${campaignId}/reset-sources`, {
      method: "POST", headers: authHeader(),
    })
    if (!r.ok) { const e = await r.json(); alert(e.detail || "Failed to reset sources"); return }
    qc.invalidateQueries({ queryKey: ["campaign", campaignId] })
  }

  async function deleteSource(id: string) {
    if (!confirm("Remove this source?")) return
    await fetch(`${API}/api/outreach/sources/${id}`, { method: "DELETE", headers: authHeader() })
    qc.invalidateQueries({ queryKey: ["campaign", campaignId] })
  }

  async function approveAllDrafts() {
    const pending = (draftsData?.items || []).filter((d: any) => d.status === "pending_review")
    for (const d of pending) {
      await fetch(`${API}/api/outreach/drafts/${d.id}`, {
        method: "PATCH",
        headers: { ...authHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({ status: "approved" }),
      })
    }
    qc.invalidateQueries({ queryKey: ["drafts", campaignId] })
  }

  if (isLoading) return <div className="p-8 text-center text-sm text-on-surface-variant">Loading…</div>
  if (!campaign) return null

  const sources = campaign.sources || []
  const platform = campaign.platform || "email"
  const drafts = draftsData?.items || []
  const pendingDrafts = (draftsData?.items || []).filter((d: any) => d.status === "pending_review").length

  const scheduleLabel = campaign.auto_search_enabled
    ? campaign.next_search_at
      ? `Next: ${new Date(campaign.next_search_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`
      : "Scheduled"
    : "Manual"

  const tabs = [
    { id: "leads",    label: `Leads (${leadsData?.total ?? 0})`, icon: "group" },
    { id: "drafts",   label: `Drafts${pendingDrafts > 0 ? ` (${pendingDrafts})` : ""}`, icon: "mail" },
    { id: "personas", label: "Personas", icon: "groups" },
    { id: "sources",  label: `Sources (${sources.length})`, icon: "travel_explore" },
  ]

  return (
    <>
      {showFindLeads && (
        <FindLeadsModal campaignId={campaignId} onClose={() => setShowFindLeads(false)}
          onTriggered={() => {
            startSearchPolling()
            qc.invalidateQueries({ queryKey: ["leads", campaignId] })
          }} />
      )}
      {showAddSource && (
        <AddSourceModal campaignId={campaignId} onClose={() => setShowAddSource(false)}
          onAdded={() => qc.invalidateQueries({ queryKey: ["campaign", campaignId] })} />
      )}

      <div className="space-y-5">
        {/* Campaign header */}
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-5">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <h2 className="font-headline font-bold text-lg text-on-surface">{campaign.name}</h2>
                <StatusBadge status={campaign.status} />
                <PlatformBadge platform={platform} />
                {(campaign.use_mock_leads || campaign.dry_run) && (
                  <span className="text-[10px] font-label font-semibold px-2 py-0.5 rounded bg-violet-100 text-violet-700 flex items-center gap-0.5">
                    <span className="material-symbols-outlined text-[10px]">science</span>TEST MODE
                  </span>
                )}
                <span className={`text-[10px] font-label font-semibold px-2 py-0.5 rounded ${campaign.auto_search_enabled ? "bg-primary/10 text-primary" : "bg-surface-container text-on-surface-variant"}`}>
                  <span className="material-symbols-outlined text-[10px] mr-0.5">schedule</span>
                  {scheduleLabel}
                </span>
              </div>
              {campaign.goal && <p className="text-sm text-on-surface-variant leading-relaxed">{campaign.goal}</p>}
              {campaign.personas?.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {campaign.personas.map((p: any, i: number) => (
                    p.id && onOpenPersona ? (
                      <button key={p.id} onClick={() => onOpenPersona(p.id)}
                        className="text-[10px] px-2 py-0.5 rounded bg-tertiary/10 text-tertiary font-bold uppercase hover:bg-tertiary/20 transition-colors">
                        {p.name}
                      </button>
                    ) : (
                      <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-tertiary/10 text-tertiary font-bold uppercase">
                        {p.name}
                      </span>
                    )
                  ))}
                </div>
              )}
              <div className="flex items-center gap-4 mt-3 pt-3 border-t border-outline-variant/10">
                <span className="text-[10px] font-bold uppercase tracking-widest text-violet-700 flex items-center gap-1">
                  <span className="material-symbols-outlined text-[11px]">science</span>Test Mode
                </span>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={!!campaign.use_mock_leads}
                    onChange={e => patchCampaign({ use_mock_leads: e.target.checked })}
                    className="w-3.5 h-3.5 accent-violet-600" />
                  <span className="text-xs font-label text-on-surface">Mock leads</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={!!campaign.dry_run}
                    onChange={e => patchCampaign({ dry_run: e.target.checked })}
                    className="w-3.5 h-3.5 accent-violet-600" />
                  <span className="text-xs font-label text-on-surface">Dry-run sends</span>
                </label>
              </div>
              <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-outline-variant/10">
                <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant flex items-center gap-1">
                  <span className="material-symbols-outlined text-[11px]">schedule</span>Search Schedule
                </span>
                {SEARCH_INTERVALS.map(opt => {
                  const current = campaign.auto_search_enabled ? campaign.search_interval_hours ?? null : null
                  return (
                    <button key={String(opt.value)} onClick={() => patchSchedule(opt.value)}
                      className={`px-2.5 py-1 rounded-lg text-[11px] font-label font-semibold border transition-colors ${current === opt.value ? "border-primary bg-primary/5 text-primary" : "border-outline-variant/20 text-on-surface-variant hover:border-primary/30"}`}>
                      {opt.label}
                    </button>
                  )
                })}
              </div>
            </div>
            <div className="flex flex-wrap items-start gap-2">
              <button onClick={() => setShowFindLeads(true)} disabled={!!actionLoading}
                className="flex items-center gap-1.5 px-3 py-2 bg-surface-container text-on-surface text-xs font-label font-semibold rounded-lg hover:bg-surface-dim disabled:opacity-50 transition-colors">
                <span className="material-symbols-outlined text-[14px]">search</span>Find Leads
              </button>
              <button onClick={() => triggerAction("compose-pending", {}, "compose")} disabled={!!actionLoading}
                className="flex items-center gap-1.5 px-3 py-2 bg-surface-container text-on-surface text-xs font-label font-semibold rounded-lg hover:bg-surface-dim disabled:opacity-50 transition-colors">
                <span className="material-symbols-outlined text-[14px]">auto_awesome</span>
                {actionLoading === "compose" ? "Drafting…" : "Generate Drafts"}
              </button>
              <button onClick={() => triggerAction("send-approved", {}, "send")} disabled={!!actionLoading}
                className="flex items-center gap-1.5 px-3 py-2 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity">
                <span className="material-symbols-outlined text-[14px]">send</span>
                {actionLoading === "send" ? "Sending…" : "Send Approved"}
              </button>
              {onEdit && (
                <button onClick={onEdit}
                  className="flex items-center gap-1.5 px-3 py-2 bg-surface-container text-on-surface text-xs font-label font-semibold rounded-lg hover:bg-surface-dim transition-colors">
                  <span className="material-symbols-outlined text-[14px]">edit</span>
                  Edit
                </button>
              )}
              <button onClick={cloneCampaign} disabled={cloning || !!actionLoading}
                className="flex items-center gap-1.5 px-3 py-2 bg-surface-container text-on-surface text-xs font-label font-semibold rounded-lg hover:bg-surface-dim disabled:opacity-50 transition-colors">
                <span className="material-symbols-outlined text-[14px]">content_copy</span>
                {cloning ? "Cloning…" : "Clone"}
              </button>
              <button onClick={deleteCampaign} disabled={deleting}
                className="flex items-center gap-1.5 px-3 py-2 border border-error/30 text-error text-xs font-label font-semibold rounded-lg hover:bg-error-container disabled:opacity-50 transition-colors">
                <span className="material-symbols-outlined text-[14px]">delete</span>
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>

          {/* Stats bar */}
          <div className="flex items-center gap-6 mt-4 pt-4 border-t border-outline-variant/10 text-xs font-label text-on-surface-variant">
            <span><strong className="text-on-surface">{campaign.leads_count}</strong> leads</span>
            <span><strong className="text-on-surface">{campaign.drafts_pending}</strong> drafts pending</span>
            <span><strong className="text-on-surface">{campaign.total_sends}</strong> sent</span>
            {campaign.total_sends > 0 && <span><strong className="text-on-surface">{campaign.reply_rate}%</strong> reply rate</span>}
          </div>

          {/* Search banner */}
          {searchingLeads && (
            <div className="flex items-center justify-between gap-3 mt-3 px-3 py-2.5 bg-primary/8 border border-primary/20 rounded-lg">
              <div className="flex items-center gap-2 text-xs font-label text-primary">
                <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>
                Searching across all sources — {leadsData?.total ?? 0} leads found so far.
              </div>
              <button onClick={() => setSearchingLeads(false)} className="text-primary/60 hover:text-primary">
                <span className="material-symbols-outlined text-[16px]">close</span>
              </button>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-surface-container-low p-1 rounded-xl w-fit">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id as any)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-label font-semibold transition-colors ${activeTab === t.id ? "bg-surface-container-lowest text-on-surface shadow-float" : "text-on-surface-variant hover:text-on-surface"}`}>
              <span className="material-symbols-outlined text-[14px]">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>

        {/* Leads tab */}
        {activeTab === "leads" && (
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 overflow-hidden">
            {!leadsData?.items?.length ? (
              <div className="p-8 text-center">
                <span className="material-symbols-outlined text-[40px] text-on-surface-variant/30 block mb-3">group</span>
                <p className="text-sm text-on-surface-variant">No leads yet.</p>
                <p className="text-xs text-on-surface-variant mt-1">Click "Find Leads" to search across your configured sources.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-container-low border-b border-outline-variant/10">
                      {["Name", "Channel", "Their Post", "Persona", "Intent", "Company / Website", "Status"].map(h => (
                        <th key={h} className="px-4 py-2.5 text-left text-[10px] font-label font-semibold uppercase tracking-wider text-on-surface-variant whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/10">
                    {leadsData.items.map((l: any) => (
                      <tr key={l.id} className="hover:bg-surface-container-low/40 transition-colors">
                        <td className="px-4 py-3 text-sm font-label text-on-surface whitespace-nowrap">
                          {l.name || l.platform_username || "—"}
                        </td>
                        <td className="px-4 py-3">
                          {l.source_url
                            ? <a href={l.source_url} target="_blank" rel="noopener noreferrer">
                                <PlatformBadge platform={l.source_channel} small />
                              </a>
                            : <PlatformBadge platform={l.source_channel} small />}
                        </td>
                        <td className="px-4 py-3 text-xs text-on-surface-variant max-w-[240px]">
                          <span className="line-clamp-2">{l.context || l.notes || "—"}</span>
                        </td>
                        <td className="px-4 py-3">
                          {l.matched_persona
                            ? <span className="text-[10px] px-2 py-0.5 rounded bg-tertiary/10 text-tertiary font-bold uppercase">{l.matched_persona}</span>
                            : <span className="text-xs text-on-surface-variant">—</span>}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          {l.intent_score != null ? (
                            <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                              l.intent_score >= 70 ? "bg-green-500/15 text-green-700 dark:text-green-400"
                              : l.intent_score >= 50 ? "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400"
                              : "bg-surface-container text-on-surface-variant"
                            }`}>{l.intent_score}</span>
                          ) : <span className="text-xs text-on-surface-variant">—</span>}
                        </td>
                        <td className="px-4 py-3 text-xs text-on-surface-variant max-w-[140px] truncate">
                          {l.company || l.website_url || "—"}
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

        {/* Drafts tab */}
        {activeTab === "drafts" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex gap-1 bg-surface-container-low p-1 rounded-lg">
                {[
                  { id: "pending_review", label: "Pending" },
                  { id: "approved", label: "Approved" },
                  { id: "awaiting_send", label: "To Send" },
                  { id: "rejected", label: "Rejected" },
                  { id: "test_sent", label: "Test Sent" },
                  { id: "", label: "All" },
                ].map(f => (
                  <button key={f.id} onClick={() => setDraftStatusFilter(f.id)}
                    className={`px-3 py-1.5 rounded text-xs font-label font-semibold transition-colors ${draftStatusFilter === f.id ? "bg-surface-container-lowest text-on-surface shadow-sm" : "text-on-surface-variant hover:text-on-surface"}`}>
                    {f.label}
                  </button>
                ))}
              </div>
              {draftStatusFilter === "pending_review" && drafts.length > 1 && (
                <button onClick={approveAllDrafts}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white text-xs font-label font-semibold rounded-lg hover:bg-emerald-700 transition-colors">
                  <span className="material-symbols-outlined text-[13px]">done_all</span>Approve All
                </button>
              )}
            </div>

            {!drafts.length ? (
              <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-8 text-center">
                <span className="material-symbols-outlined text-[40px] text-on-surface-variant/30 block mb-3">mail_outline</span>
                <p className="text-sm text-on-surface-variant">
                  {draftStatusFilter === "pending_review" ? "No drafts awaiting review." : `No ${draftStatusFilter.replace("_", " ")} drafts.`}
                </p>
                {draftStatusFilter === "pending_review" && (
                  <p className="text-xs text-on-surface-variant mt-1">Click "Generate Drafts" to write personalized messages for your leads.</p>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                {drafts.map((d: any) => (
                  <DraftCard key={d.id} draft={d}
                    onUpdate={() => { refetchDrafts(); qc.invalidateQueries({ queryKey: ["campaign", campaignId] }) }} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Personas tab */}
        {activeTab === "personas" && (
          <PersonaLibrary campaignId={campaignId} venture={campaign.venture} onOpenPersona={onOpenPersona} />
        )}

        {/* Sources tab */}
        {activeTab === "sources" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs text-on-surface-variant">
                Each source is searched when you run "Find Leads" or on the scheduled interval.
              </p>
              <div className="flex items-center gap-2">
                <button onClick={resetSources}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg hover:bg-surface-container-high transition-colors border border-outline-variant/30"
                  title="Replace all sources with venture defaults">
                  <span className="material-symbols-outlined text-[14px]">restart_alt</span>Reset to Defaults
                </button>
                <button onClick={() => setShowAddSource(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg hover:opacity-90 transition-opacity">
                  <span className="material-symbols-outlined text-[14px]">add</span>Add Source
                </button>
              </div>
            </div>
            {!sources.length ? (
              <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-8 text-center">
                <p className="text-sm text-on-surface-variant">No sources configured.</p>
              </div>
            ) : (
              sources.map((s: any) => (
                <SourceRow key={s.id} source={s}
                  onSave={patchSource} onDelete={deleteSource} />
              ))
            )}
          </div>
        )}
      </div>
    </>
  )
}

// ── Contacts section ───────────────────────────────────────────────────────────────────────

function ContactsSection() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [searchInput, setSearchInput] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [showNewContact, setShowNewContact] = useState(false)
  const { data, isLoading } = useContacts(page, search, statusFilter)
  const qc = useQueryClient()

  async function updateContact(id: string, is_test_user: boolean) {
    await fetch(`${API}/api/outreach/contacts/${id}`, {
      method: "PATCH",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({ is_test_user }),
    })
    qc.invalidateQueries({ queryKey: ["contacts"] })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2 bg-surface-container-lowest rounded-lg border border-outline-variant/20 px-3 py-2">
          <span className="material-symbols-outlined text-[16px] text-on-surface-variant">search</span>
          <input value={searchInput} onChange={e => setSearchInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") { setSearch(searchInput); setPage(1) } }}
            placeholder="Search email, name, company…"
            className="text-sm font-label text-on-surface bg-transparent outline-none w-56" />
        </div>
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm font-label bg-surface-container-lowest rounded-lg border border-outline-variant/20 text-on-surface">
          <option value="">All statuses</option>
          <option value="approached">Approached</option>
          <option value="inquired">Inquired</option>
          <option value="purchased">Purchased</option>
          <option value="unsubscribed">Unsubscribed</option>
        </select>
        <span className="text-xs text-on-surface-variant font-label">{data ? `${data.total} contacts` : ""}</span>
        <button onClick={() => setShowNewContact(true)}
          className="ml-auto flex items-center gap-1 px-3 py-2 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg hover:opacity-90 transition-opacity">
          <span className="material-symbols-outlined text-[14px]">add</span>Create Contact
        </button>
      </div>

      {showNewContact && (
        <NewContactModal onClose={() => setShowNewContact(false)}
          onCreated={() => qc.invalidateQueries({ queryKey: ["contacts"] })} />
      )}

      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-on-surface-variant">Loading…</div>
        ) : !data?.items?.length ? (
          <div className="p-8 text-center">
            <span className="material-symbols-outlined text-[40px] text-on-surface-variant/30 block mb-3">contacts</span>
            <p className="text-sm text-on-surface-variant">No contacts yet.</p>
            <p className="text-xs text-on-surface-variant mt-1">Contacts are created when leads are emailed.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant/10">
                  {["Name", "Email", "Company", "Status", "Test", "Ventures", "Last Activity"].map(h => (
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
                    <td className="px-4 py-3 text-center">
                      <input type="checkbox" defaultChecked={c.is_test_user}
                        onChange={e => updateContact(c.id, e.target.checked)}
                        className="h-4 w-4 bg-surface-container border-outline-variant/30 rounded text-primary focus:ring-primary" />
                    </td>
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

// ── New Campaign form ──────────────────────────────────────────────────────────────────────

function CampaignForm({ campaign, onSaved, onCancel }: {
  campaign?: any
  onSaved: (id: string) => void
  onCancel: () => void
}) {
  const isEdit = !!campaign
  const [product, setProduct] = useState(campaign?.venture || "marketing_audit")
  const [name, setName] = useState(campaign?.name || "")
  const [goal, setGoal] = useState(campaign?.goal || "")
  const [sources, setSources] = useState<SourceObj[]>(
    (campaign?.sources || []).map((s: any) => ({
      id: s.id, platform: s.platform, name: s.name,
      keywords: s.keywords || [], config: s.config || {}, enabled: s.enabled ?? true,
    }))
  )
  const [removedSourceIds, setRemovedSourceIds] = useState<string[]>([])
  const [showAddSource, setShowAddSource] = useState(false)
  const [targetPrompt, setTargetPrompt] = useState(campaign?.target_prompt || "")
  const [userInstructions, setUserInstructions] = useState(campaign?.user_search_instructions || "")
  const [personas, setPersonas] = useState<{ name: string; description: string }[]>(
    (campaign?.personas || []).map((p: any) => ({ name: p.name, description: p.description }))
  )
  const [intervalHours, setIntervalHours] = useState<number | null>(
    campaign?.auto_search_enabled ? (campaign?.search_interval_hours ?? null) : null
  )
  const [useMockLeads, setUseMockLeads] = useState(!!campaign?.use_mock_leads)
  const [dryRun, setDryRun] = useState(!!campaign?.dry_run)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [templates, setTemplates] = useState<any[]>([])

  useEffect(() => {
    if (isEdit) return
    fetch(`${API}/api/outreach/persona-templates`, { headers: authHeader() })
      .then(r => r.ok ? r.json() : { items: [] })
      .then(d => setTemplates(d.items || []))
      .catch(() => {})
  }, [isEdit])

  function applyTemplate(tpl: any) {
    setProduct(tpl.venture || "content_repurposing")
    setTargetPrompt(tpl.target_prompt || "")
    if (tpl.personas?.length) setPersonas(tpl.personas)
    if (tpl.name && !name.trim()) setName(tpl.name)
  }

  function removeSource(i: number) {
    const s = sources[i]
    if (s.id) setRemovedSourceIds(prev => [...prev, s.id!])
    setSources(prev => prev.filter((_, j) => j !== i))
  }

  const corePayload = () => ({
    name: name.trim(), goal: goal.trim() || null,
    personas: personas.filter(p => p.name.trim()),
    target_prompt: targetPrompt.trim() || null,
    user_search_instructions: userInstructions.trim() || null,
    use_mock_leads: useMockLeads,
    dry_run: dryRun,
  })

  async function save() {
    if (!name.trim()) { setError("Campaign name is required."); return }
    if (sources.length === 0) { setError("Add at least one search source before saving."); return }
    setError("")
    setSaving(true)
    try {
      if (!isEdit) {
        const r = await fetch(`${API}/api/outreach/campaigns`, {
          method: "POST",
          headers: { ...authHeader(), "Content-Type": "application/json" },
          body: JSON.stringify({
            venture: product, sources,
            auto_search_enabled: intervalHours !== null,
            search_interval_hours: intervalHours,
            ...corePayload(),
          }),
        })
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Failed to create campaign.")
        onSaved((await r.json()).id)
        return
      }

      // Edit: patch core fields, schedule, then reconcile sources.
      const id = campaign.id
      const rc = await fetch(`${API}/api/outreach/campaigns/${id}`, {
        method: "PATCH", headers: { ...authHeader(), "Content-Type": "application/json" },
        body: JSON.stringify(corePayload()),
      })
      if (!rc.ok) throw new Error((await rc.json().catch(() => ({}))).detail || "Failed to save campaign.")
      await fetch(`${API}/api/outreach/campaigns/${id}/schedule`, {
        method: "PATCH", headers: { ...authHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({ auto_search_enabled: intervalHours !== null, search_interval_hours: intervalHours }),
      })
      for (const sid of removedSourceIds) {
        await fetch(`${API}/api/outreach/sources/${sid}`, { method: "DELETE", headers: authHeader() })
      }
      for (const s of sources.filter(s => !s.id)) {
        await fetch(`${API}/api/outreach/campaigns/${id}/sources`, {
          method: "POST", headers: { ...authHeader(), "Content-Type": "application/json" },
          body: JSON.stringify({ platform: s.platform, name: s.name, keywords: s.keywords, config: s.config, enabled: s.enabled }),
        })
      }
      onSaved(id)
    } catch (e: any) {
      setError(e.message || "Failed to save campaign.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-4 space-y-4">
      {showAddSource && (
        <AddSourceModal onClose={() => setShowAddSource(false)}
          onSubmit={(s) => setSources(prev => [...prev, s])} />
      )}
      {/* Persona templates (create only) */}
      {!isEdit && templates.length > 0 && (
        <div>
          <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">
            Start from a template
          </label>
          <div className="flex flex-wrap gap-2">
            {templates.map((tpl: any) => (
              <button key={tpl.key} onClick={() => applyTemplate(tpl)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-label font-semibold border border-primary/30 text-primary bg-primary/5 hover:bg-primary/10 transition-colors">
                <span className="material-symbols-outlined text-[14px]">auto_awesome</span>
                {tpl.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Product */}
      <div>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Product</label>
        <select value={product} onChange={e => setProduct(e.target.value)} disabled={isEdit}
          className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface disabled:opacity-60">
          {PRODUCTS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
      </div>

      {/* Name */}
      <div>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Campaign Name</label>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Reddit Q2 Outreach"
          className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
      </div>

      {/* Search sources */}
      <div>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">
          Search Sources
          <span className="ml-1 text-on-surface-variant/60 normal-case font-normal">(where we look for leads — at least one required)</span>
        </label>
        {sources.length > 0 && (
          <div className="space-y-1.5 mb-2">
            {sources.map((s, i) => {
              const info = SOURCE_PLATFORMS.find(p => p.id === s.platform)
              return (
                <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-container-low border border-outline-variant/20">
                  <span className="material-symbols-outlined text-[15px] text-primary">{info?.icon || "travel_explore"}</span>
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-label font-semibold text-on-surface">{s.name}</span>
                    <span className="text-[10px] text-on-surface-variant ml-1.5">{info?.label || s.platform} · {s.keywords.length} keyword{s.keywords.length === 1 ? "" : "s"}</span>
                  </div>
                  <button onClick={() => removeSource(i)}
                    className="text-on-surface-variant hover:text-error">
                    <span className="material-symbols-outlined text-[16px]">close</span>
                  </button>
                </div>
              )
            })}
          </div>
        )}
        <button onClick={() => setShowAddSource(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-label font-semibold border border-primary/30 text-primary bg-primary/5 hover:bg-primary/10 transition-colors">
          <span className="material-symbols-outlined text-[14px]">add</span>Add Source
        </button>
      </div>

      {/* Goal */}
      <div>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Campaign Goal</label>
        <textarea value={goal} onChange={e => setGoal(e.target.value)}
          placeholder="What outcome do you want? (e.g. drive trial sign-ups for the free marketing audit)"
          rows={2}
          className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none" />
      </div>

      {/* Target prompt */}
      <div>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">
          Product &amp; Audience Context
          <span className="ml-1 text-on-surface-variant/60 normal-case font-normal">(feeds AI search + message writing)</span>
        </label>
        <textarea value={targetPrompt} onChange={e => setTargetPrompt(e.target.value)}
          placeholder="Describe what we're selling, who the ideal buyer is, what pain point we solve, and what makes us different. Claude uses this when searching for leads and writing personalized messages."
          rows={4}
          className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none leading-relaxed" />
      </div>

      {/* Personas */}
      <div>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">
          Customer Personas
          <span className="ml-1 text-on-surface-variant/60 normal-case font-normal">(up to 5 — used to qualify and match leads)</span>
        </label>
        <PersonaEditor personas={personas} onChange={setPersonas} />
      </div>

      {/* Search instructions */}
      <div>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">
          Search Instructions
          <span className="ml-1 text-on-surface-variant/60 normal-case font-normal">(optional — specific guidance or exclusions)</span>
        </label>
        <textarea value={userInstructions} onChange={e => setUserInstructions(e.target.value)}
          placeholder="e.g. Focus on bootstrapped founders only. Exclude enterprise companies. Skip posts from agencies."
          rows={2}
          className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none" />
      </div>

      {/* Search schedule */}
      <div>
        <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Search Schedule</label>
        <div className="flex gap-2">
          {SEARCH_INTERVALS.map(opt => (
            <button key={String(opt.value)} onClick={() => setIntervalHours(opt.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-label font-semibold border transition-colors ${intervalHours === opt.value ? "border-primary bg-primary/5 text-primary" : "border-outline-variant/20 text-on-surface-variant hover:border-primary/30"}`}>
              {opt.label}
            </button>
          ))}
        </div>
        <p className="text-[10px] text-on-surface-variant mt-1">
          {intervalHours ? `Automatically searches and drafts messages every ${intervalHours}h.` : "Search manually using the Find Leads button."}
        </p>
      </div>

      {/* Test Mode */}
      <div className="border border-violet-200 bg-violet-50/50 rounded-lg p-3 space-y-2">
        <p className="text-[10px] font-bold uppercase tracking-widest text-violet-700 flex items-center gap-1">
          <span className="material-symbols-outlined text-[12px]">science</span>Test Mode
        </p>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={useMockLeads} onChange={e => setUseMockLeads(e.target.checked)}
            className="w-3.5 h-3.5 accent-violet-600" />
          <span className="text-xs font-label text-on-surface">Use mock leads</span>
          <span className="text-[10px] text-on-surface-variant">(skip real platform searches — use fixture data)</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={dryRun} onChange={e => setDryRun(e.target.checked)}
            className="w-3.5 h-3.5 accent-violet-600" />
          <span className="text-xs font-label text-on-surface">Dry-run sends</span>
          <span className="text-[10px] text-on-surface-variant">(mark drafts as test_sent — no real emails sent)</span>
        </label>
      </div>

      {error && <p className="text-xs text-error">{error}</p>}

      <div className="flex gap-2 pt-1">
        <button onClick={save} disabled={saving}
          className="px-4 py-1.5 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg disabled:opacity-50">
          {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Campaign"}
        </button>
        <button onClick={onCancel} className="px-4 py-1.5 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg">
          Cancel
        </button>
      </div>
    </div>
  )
}

// ── Personas page ───────────────────────────────────────────────────────────────────────

function PersonasPage({ focusPersonaId }: { focusPersonaId?: string | null }) {
  const [items, setItems] = useState<any[]>([])
  const [ventureFilter, setVentureFilter] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [newVenture, setNewVenture] = useState(PRODUCTS[0].id)
  const [newName, setNewName] = useState("")
  const [newDesc, setNewDesc] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState("")
  const [editDesc, setEditDesc] = useState("")
  const refs = useRef<Record<string, HTMLDivElement | null>>({})

  async function load() {
    setLoading(true)
    const q = ventureFilter ? `?venture=${ventureFilter}` : ""
    const d = await fetch(`${API}/api/outreach/personas${q}`, { headers: authHeader() }).then(r => r.json())
    setItems(d.items || [])
    setLoading(false)
  }
  useEffect(() => { load() }, [ventureFilter])

  useEffect(() => {
    if (focusPersonaId && refs.current[focusPersonaId]) {
      refs.current[focusPersonaId]?.scrollIntoView({ behavior: "smooth", block: "center" })
    }
  }, [focusPersonaId, items])

  async function createPersona() {
    if (!newName.trim()) return
    setSaving(true)
    await fetch(`${API}/api/outreach/personas`, {
      method: "POST", headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({ venture: newVenture, name: newName.trim(), description: newDesc.trim() }),
    })
    setNewName(""); setNewDesc(""); setSaving(false)
    await load()
  }
  function startEdit(p: any) { setEditingId(p.id); setEditName(p.name); setEditDesc(p.description) }
  async function saveEdit(id: string) {
    setSaving(true)
    await fetch(`${API}/api/outreach/personas/${id}`, {
      method: "PATCH", headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({ name: editName, description: editDesc }),
    })
    setEditingId(null); setSaving(false)
    await load()
  }
  async function deletePersona(p: any) {
    if (!window.confirm(`Delete persona "${p.name}"? It will be unlinked from all campaigns.`)) return
    await fetch(`${API}/api/outreach/personas/${p.id}?force=true`, { method: "DELETE", headers: authHeader() })
    await load()
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div className="lg:col-span-8 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-headline font-bold text-sm text-on-surface">Persona Library</h2>
          <select value={ventureFilter} onChange={e => setVentureFilter(e.target.value)}
            className="px-3 py-1.5 text-xs font-label bg-surface-container-lowest rounded-lg border border-outline-variant/20 text-on-surface">
            <option value="">All products</option>
            {PRODUCTS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </div>
        <p className="text-xs text-on-surface-variant">
          Personas are reusable across campaigns. Editing a persona updates every campaign linked to it.
        </p>

        {loading ? (
          <p className="text-sm text-on-surface-variant">Loading…</p>
        ) : !items.length ? (
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-8 text-center">
            <span className="material-symbols-outlined text-[40px] text-on-surface-variant/30 block mb-3">groups</span>
            <p className="text-sm text-on-surface-variant">No personas yet — create one on the right.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map(p => {
              const product = PRODUCTS.find(x => x.id === p.venture)
              const focused = p.id === focusPersonaId
              return (
                <div key={p.id} ref={el => { refs.current[p.id] = el }}
                  className={`bg-surface-container-lowest rounded-xl border p-4 transition-colors ${focused ? "border-primary ring-2 ring-primary/30" : "border-outline-variant/20"}`}>
                  {editingId === p.id ? (
                    <div className="space-y-2">
                      <input value={editName} onChange={e => setEditName(e.target.value)}
                        className="w-full px-3 py-1.5 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
                      <textarea value={editDesc} onChange={e => setEditDesc(e.target.value)} rows={6}
                        className="w-full px-3 py-1.5 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none leading-relaxed" />
                      <div className="flex gap-2">
                        <button onClick={() => saveEdit(p.id)} disabled={saving}
                          className="px-3 py-1.5 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg disabled:opacity-50">Save</button>
                        <button onClick={() => setEditingId(null)}
                          className="px-3 py-1.5 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg">Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-start justify-between gap-3 mb-1">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-label font-semibold text-on-surface">{p.name}</p>
                          {product && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant font-bold uppercase tracking-wider">{product.label}</span>
                          )}
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <button onClick={() => startEdit(p)} className="text-on-surface-variant hover:text-primary transition-colors">
                            <span className="material-symbols-outlined text-[16px]">edit</span>
                          </button>
                          <button onClick={() => deletePersona(p)} className="text-on-surface-variant hover:text-error transition-colors">
                            <span className="material-symbols-outlined text-[16px]">delete</span>
                          </button>
                        </div>
                      </div>
                      <p className="text-xs text-on-surface-variant leading-relaxed whitespace-pre-wrap">{p.description}</p>
                    </>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="lg:col-span-4">
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-4 space-y-3 sticky top-4">
          <h3 className="font-headline font-bold text-sm text-on-surface">New Persona</h3>
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Product</label>
            <select value={newVenture} onChange={e => setNewVenture(e.target.value)}
              className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface">
              {PRODUCTS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </div>
          <input value={newName} onChange={e => setNewName(e.target.value)} placeholder='Name (e.g. "Amir — Small Business Owner")'
            className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
          <textarea value={newDesc} onChange={e => setNewDesc(e.target.value)} rows={6}
            placeholder="Describe the persona — profile, characteristics, pain points, triggers, audience attributes…"
            className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface resize-none leading-relaxed" />
          <button onClick={createPersona} disabled={saving || !newName.trim()}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-primary text-on-primary rounded-lg text-xs font-label font-semibold disabled:opacity-50 transition-colors">
            <span className="material-symbols-outlined text-[14px]">add</span>Create Persona
          </button>
        </div>
      </div>
    </div>
  )
}

// ── New contact modal ───────────────────────────────────────────────────────────────────

function NewContactModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [company, setCompany] = useState("")
  const [website, setWebsite] = useState("")
  const [phone, setPhone] = useState("")
  const [statusVal, setStatusVal] = useState("approached")
  const [venture, setVenture] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  async function save() {
    if (!name.trim() && !email.trim()) { setError("Provide at least a name or an email."); return }
    setError(""); setSaving(true)
    const r = await fetch(`${API}/api/outreach/contacts`, {
      method: "POST", headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name.trim() || null, email: email.trim() || null,
        company: company.trim() || null, website_url: website.trim() || null,
        phone: phone.trim() || null, status: statusVal, venture: venture || null,
      }),
    })
    setSaving(false)
    if (r.ok) { onCreated(); onClose() }
    else setError((await r.json().catch(() => ({}))).detail || "Failed to create contact.")
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/20 shadow-float w-full max-w-md">
        <div className="px-6 py-4 border-b border-outline-variant/10 flex items-center justify-between">
          <h3 className="font-headline font-bold text-base text-on-surface">Create Contact</h3>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface">
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>
        <div className="p-6 space-y-3">
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Name"
            className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
          <input value={email} onChange={e => setEmail(e.target.value)} placeholder="Email"
            className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
          <div className="grid grid-cols-2 gap-3">
            <input value={company} onChange={e => setCompany(e.target.value)} placeholder="Company"
              className="px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
            <input value={phone} onChange={e => setPhone(e.target.value)} placeholder="Phone"
              className="px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
          </div>
          <input value={website} onChange={e => setWebsite(e.target.value)} placeholder="Website URL"
            className="w-full px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface" />
          <div className="grid grid-cols-2 gap-3">
            <select value={statusVal} onChange={e => setStatusVal(e.target.value)}
              className="px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface">
              <option value="approached">Approached</option>
              <option value="inquired">Inquired</option>
              <option value="purchased">Purchased</option>
              <option value="unsubscribed">Unsubscribed</option>
            </select>
            <select value={venture} onChange={e => setVenture(e.target.value)}
              className="px-3 py-2 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface">
              <option value="">No product tag</option>
              {PRODUCTS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </div>
          {error && <p className="text-xs text-error">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button onClick={save} disabled={saving}
              className="px-4 py-1.5 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg disabled:opacity-50">
              {saving ? "Saving…" : "Create Contact"}
            </button>
            <button onClick={onClose} className="px-4 py-1.5 bg-surface-container text-on-surface-variant text-xs font-label font-semibold rounded-lg">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Campaigns table ─────────────────────────────────────────────────────────────────────

function scheduleLabel(c: any): string {
  if (!c.auto_search_enabled || !c.search_interval_hours) return "Manual"
  const m: Record<number, string> = { 6: "Every 6h", 24: "Daily", 168: "Weekly" }
  return m[c.search_interval_hours] || `Every ${c.search_interval_hours}h`
}

function Truncated({ text, className = "" }: { text: string; className?: string }) {
  return <span title={text} className={`block truncate ${className}`}>{text || "—"}</span>
}

function CampaignsTable({ campaigns, onRow, onEdit, onDelete, onOpenPersona }: {
  campaigns: any[]
  onRow: (id: string) => void
  onEdit: (id: string) => void
  onDelete: (id: string) => void
  onOpenPersona: (id: string) => void
}) {
  const cols = ["Product", "Campaign", "Sources", "Goal", "Audience Context", "Personas", "Schedule", "Test Mode", ""]
  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm table-fixed">
          <thead>
            <tr className="bg-surface-container-low border-b border-outline-variant/10">
              {cols.map((h, i) => (
                <th key={i} className="px-3 py-2.5 text-left text-[10px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/10">
            {campaigns.map((c: any) => {
              const product = PRODUCTS.find(p => p.id === c.venture)
              const sourceLabels = (c.sources || []).map((s: any) =>
                SOURCE_PLATFORMS.find(p => p.id === s.platform)?.label || s.platform).join(", ")
              const testOn = c.use_mock_leads || c.dry_run
              return (
                <tr key={c.id} onClick={() => onRow(c.id)}
                  className="hover:bg-surface-container-low/50 cursor-pointer align-top">
                  <td className="px-3 py-3 w-[8%]"><Truncated text={product?.label || c.venture} className="text-xs text-on-surface-variant" /></td>
                  <td className="px-3 py-3 w-[12%] text-sm font-label font-semibold text-on-surface"><Truncated text={c.name} /></td>
                  <td className="px-3 py-3 w-[12%]"><Truncated text={sourceLabels} className="text-xs text-on-surface-variant" /></td>
                  <td className="px-3 py-3 w-[14%]"><Truncated text={c.goal || ""} className="text-xs text-on-surface-variant" /></td>
                  <td className="px-3 py-3 w-[16%]"><Truncated text={c.target_prompt || ""} className="text-xs text-on-surface-variant" /></td>
                  <td className="px-3 py-3 w-[12%]">
                    <div className="flex flex-wrap gap-1">
                      {(c.personas || []).slice(0, 3).map((p: any, i: number) => (
                        p.id ? (
                          <button key={p.id} onClick={e => { e.stopPropagation(); onOpenPersona(p.id) }}
                            title={p.name}
                            className="max-w-[90px] truncate text-[9px] px-1.5 py-0.5 rounded bg-tertiary/10 text-tertiary font-bold uppercase hover:bg-tertiary/20 transition-colors">{p.name}</button>
                        ) : (
                          <span key={i} title={p.name} className="max-w-[90px] truncate text-[9px] px-1.5 py-0.5 rounded bg-tertiary/10 text-tertiary font-bold uppercase">{p.name}</span>
                        )
                      ))}
                      {(c.personas?.length || 0) > 3 && <span className="text-[9px] text-on-surface-variant">+{c.personas.length - 3}</span>}
                      {!(c.personas?.length) && <span className="text-xs text-on-surface-variant">—</span>}
                    </div>
                  </td>
                  <td className="px-3 py-3 w-[9%] text-xs text-on-surface-variant whitespace-nowrap">{scheduleLabel(c)}</td>
                  <td className="px-3 py-3 w-[9%]">
                    {testOn ? (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-violet-100 text-violet-700 font-bold uppercase whitespace-nowrap">
                        {[c.use_mock_leads && "Mock", c.dry_run && "Dry-run"].filter(Boolean).join(" + ")}
                      </span>
                    ) : <span className="text-xs text-on-surface-variant">Off</span>}
                  </td>
                  <td className="px-3 py-3 w-[8%]">
                    <div className="flex gap-1 justify-end" onClick={e => e.stopPropagation()}>
                      <button onClick={() => onEdit(c.id)} title="Edit"
                        className="text-on-surface-variant hover:text-primary transition-colors">
                        <span className="material-symbols-outlined text-[17px]">edit</span>
                      </button>
                      <button onClick={() => onDelete(c.id)} title="Delete"
                        className="text-on-surface-variant hover:text-error transition-colors">
                        <span className="material-symbols-outlined text-[17px]">delete</span>
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Campaign popup (view / edit) ─────────────────────────────────────────────────────────

function CampaignModal({ campaignId, initialEdit, onClose, onChanged, onOpenPersona }: {
  campaignId: string
  initialEdit: boolean
  onClose: () => void
  onChanged: () => void
  onOpenPersona: (id: string) => void
}) {
  const [mode, setMode] = useState<"view" | "edit">(initialEdit ? "edit" : "view")
  const [editCampaign, setEditCampaign] = useState<any>(null)

  useEffect(() => {
    if (mode !== "edit") return
    fetch(`${API}/api/outreach/campaigns/${campaignId}`, { headers: authHeader() })
      .then(r => r.json()).then(setEditCampaign).catch(() => {})
  }, [mode, campaignId])

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/20 shadow-float w-full max-w-5xl my-6">
        <div className="px-6 py-3 border-b border-outline-variant/10 flex items-center justify-between sticky top-0 bg-surface-container-lowest z-10 rounded-t-2xl">
          <h3 className="font-headline font-bold text-base text-on-surface">
            {mode === "edit" ? "Edit Campaign" : "Campaign"}
          </h3>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface">
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>
        <div className="p-5">
          {mode === "view" ? (
            <CampaignDetail campaignId={campaignId}
              onDeleted={() => { onChanged(); onClose() }}
              onCloned={() => { onChanged() }}
              onEdit={() => setMode("edit")}
              onOpenPersona={onOpenPersona} />
          ) : editCampaign ? (
            <CampaignForm campaign={editCampaign}
              onSaved={() => { onChanged(); setMode("view") }}
              onCancel={() => setMode("view")} />
          ) : (
            <p className="text-sm text-on-surface-variant p-4">Loading…</p>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────────────────

type MainTab = "outreach" | "personas" | "contacts" | "paid_campaigns"

export default function Marketing() {
  const [mainTab, setMainTab] = useState<MainTab>("outreach")
  const [openCampaign, setOpenCampaign] = useState<{ id: string; edit: boolean } | null>(null)
  const [showNewCampaign, setShowNewCampaign] = useState(false)
  const [focusPersonaId, setFocusPersonaId] = useState<string | null>(null)
  const qc = useQueryClient()

  const { data: campaignsData, isLoading: campaignsLoading } = useCampaigns()

  function openPersona(id: string) {
    setOpenCampaign(null)
    setFocusPersonaId(id)
    setMainTab("personas")
  }

  async function deleteCampaign(id: string) {
    if (!window.confirm("Delete this campaign and all its leads, drafts, and sources?")) return
    await fetch(`${API}/api/outreach/campaigns/${id}`, { method: "DELETE", headers: authHeader() })
    qc.invalidateQueries({ queryKey: ["campaigns"] })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-headline font-bold text-2xl text-on-surface">Marketing</h1>
        <p className="text-sm font-body text-on-surface-variant mt-0.5">
          Persona-driven outreach, contacts, and paid campaign management
        </p>
      </div>

      <div className="flex gap-1 bg-surface-container-low p-1 rounded-xl w-fit">
        {([
          { id: "outreach",       label: "Outreach",        icon: "campaign" },
          { id: "personas",       label: "Personas",        icon: "groups" },
          { id: "contacts",       label: "Contacts",        icon: "contacts" },
          { id: "paid_campaigns", label: "Paid Campaigns",  icon: "flag" },
        ] as { id: MainTab; label: string; icon: string }[]).map(t => (
          <button key={t.id} onClick={() => { setMainTab(t.id); if (t.id !== "personas") setFocusPersonaId(null) }}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-label font-semibold transition-colors ${mainTab === t.id ? "bg-surface-container-lowest text-on-surface shadow-float" : "text-on-surface-variant hover:text-on-surface"}`}>
            <span className="material-symbols-outlined text-[14px]">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {mainTab === "personas" && <PersonasPage focusPersonaId={focusPersonaId} />}
      {mainTab === "contacts" && <ContactsSection />}
      {mainTab === "paid_campaigns" && <CampaignManager />}

      {mainTab === "outreach" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-headline font-bold text-sm text-on-surface">Campaigns</h2>
            <button onClick={() => setShowNewCampaign(true)}
              className="flex items-center gap-1 px-3 py-1.5 bg-primary text-on-primary text-xs font-label font-semibold rounded-lg hover:opacity-90 transition-opacity">
              <span className="material-symbols-outlined text-[14px]">add</span>New Campaign
            </button>
          </div>

          {campaignsLoading ? (
            <div className="h-40 bg-surface-container-lowest rounded-xl animate-pulse" />
          ) : campaignsData?.items?.length ? (
            <CampaignsTable
              campaigns={campaignsData.items}
              onRow={id => setOpenCampaign({ id, edit: false })}
              onEdit={id => setOpenCampaign({ id, edit: true })}
              onDelete={deleteCampaign}
              onOpenPersona={openPersona} />
          ) : (
            <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 p-12 text-center">
              <span className="material-symbols-outlined text-[48px] text-on-surface-variant/20 block mb-4">campaign</span>
              <p className="text-sm text-on-surface-variant">No campaigns yet.</p>
              <p className="text-xs text-on-surface-variant mt-1">Create one to start reaching out.</p>
            </div>
          )}

          {showNewCampaign && (
            <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
              <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/20 shadow-float w-full max-w-2xl my-6">
                <div className="px-6 py-3 border-b border-outline-variant/10 flex items-center justify-between">
                  <h3 className="font-headline font-bold text-base text-on-surface">New Campaign</h3>
                  <button onClick={() => setShowNewCampaign(false)} className="text-on-surface-variant hover:text-on-surface">
                    <span className="material-symbols-outlined text-[20px]">close</span>
                  </button>
                </div>
                <div className="p-5">
                  <CampaignForm
                    onSaved={id => {
                      setShowNewCampaign(false)
                      qc.invalidateQueries({ queryKey: ["campaigns"] })
                      setOpenCampaign({ id, edit: false })
                    }}
                    onCancel={() => setShowNewCampaign(false)} />
                </div>
              </div>
            </div>
          )}

          {openCampaign && (
            <CampaignModal
              campaignId={openCampaign.id}
              initialEdit={openCampaign.edit}
              onClose={() => setOpenCampaign(null)}
              onChanged={() => qc.invalidateQueries({ queryKey: ["campaigns"] })}
              onOpenPersona={openPersona} />
          )}
        </div>
      )}
    </div>
  )
}
