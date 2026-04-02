import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { getHeaders } from "../../api"
import StatusBadge from "../../components/StatusBadge"

const BASE = import.meta.env.VITE_API_URL || "https://api.planbadmin.com"

type Tab = "pipeline" | "listings"

async function triggerPhase(phase: number, params: Record<string, unknown>) {
  const res = await fetch(`${BASE}/api/ventures/etsy/phase/${phase}`, {
    method: "POST",
    headers: { ...getHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Phase ${phase} failed`)
  }
  return res.json()
}

async function fetchListings() {
  const res = await fetch(`${BASE}/api/ventures/etsy/listings`, { headers: getHeaders() })
  if (!res.ok) throw new Error("Failed to load listings")
  return res.json()
}

function PhaseCard({
  phase,
  title,
  description,
  params,
  setParams,
  onTrigger,
  isPending,
  result,
  error,
}: {
  phase: number
  title: string
  description: string
  params: Record<string, string>
  setParams: (p: Record<string, string>) => void
  onTrigger: () => void
  isPending: boolean
  result: Record<string, unknown> | null
  error: string | null
}) {
  return (
    <div className="bg-surface-container-lowest rounded-xl p-5 shadow-float space-y-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-primary-fixed flex items-center justify-center shrink-0">
            <span className="text-xs font-label font-bold text-on-primary-fixed-variant">{phase}</span>
          </div>
          <div>
            <h3 className="font-label font-semibold text-sm text-on-surface">{title}</h3>
            <p className="text-xs font-body text-on-surface-variant">{description}</p>
          </div>
        </div>
        <button
          onClick={onTrigger}
          disabled={isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-label font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 shrink-0"
        >
          {isPending ? (
            <>
              <div className="w-3 h-3 border border-on-primary border-t-transparent rounded-full animate-spin" />
              Running…
            </>
          ) : (
            <>
              <span className="material-symbols-outlined text-[14px]">play_arrow</span>
              Run
            </>
          )}
        </button>
      </div>

      {/* Optional param inputs */}
      {Object.keys(params).length > 0 && (
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(params).map(([key, val]) => (
            <div key={key}>
              <label className="block text-[10px] font-label font-medium uppercase tracking-wider text-on-surface-variant mb-1">
                {key.replace(/_/g, " ")}
              </label>
              <input
                type="text"
                value={val}
                onChange={(e) => setParams({ ...params, [key]: e.target.value })}
                className="w-full px-3 py-1.5 text-xs font-label bg-surface-container-low rounded-lg border border-transparent focus:border-primary/40 focus:outline-none text-on-surface"
              />
            </div>
          ))}
        </div>
      )}

      {error && (
        <p className="text-xs font-label text-error bg-error-container px-3 py-2 rounded-lg">{error}</p>
      )}

      {result && (
        <div className="bg-surface-container-low rounded-lg px-3 py-2">
          <p className="text-[10px] font-label font-semibold uppercase tracking-wider text-on-surface-variant mb-1">Result</p>
          <p className="text-xs font-mono text-on-surface-variant break-all">
            Task queued — job_id: {result.job_id as string ?? "—"}
          </p>
        </div>
      )}
    </div>
  )
}

function PipelineTab() {
  const qc = useQueryClient()

  type PhaseState = { params: Record<string, string>; result: Record<string, unknown> | null; error: string | null }
  const [phases, setPhases] = useState<Record<number, PhaseState>>({
    1: { params: {}, result: null, error: null },
    2: { params: { theme: "" }, result: null, error: null },
    3: { params: { subject_slug: "" }, result: null, error: null },
    4: { params: { subject_slug: "" }, result: null, error: null },
    5: { params: { subject_slug: "" }, result: null, error: null },
    6: { params: { subject_slug: "" }, result: null, error: null },
  })
  const [pending, setPending] = useState<Record<number, boolean>>({})

  async function handleTrigger(phase: number) {
    setPending((p) => ({ ...p, [phase]: true }))
    setPhases((s) => ({ ...s, [phase]: { ...s[phase], error: null, result: null } }))
    try {
      // Filter out empty params
      const rawParams = phases[phase].params
      const cleanParams = Object.fromEntries(
        Object.entries(rawParams).filter(([, v]) => v.trim() !== "")
      )
      const result = await triggerPhase(phase, cleanParams)
      setPhases((s) => ({ ...s, [phase]: { ...s[phase], result } }))
      void qc.invalidateQueries({ queryKey: ["etsyListings"] })
    } catch (e) {
      setPhases((s) => ({ ...s, [phase]: { ...s[phase], error: (e as Error).message } }))
    } finally {
      setPending((p) => ({ ...p, [phase]: false }))
    }
  }

  function setParams(phase: number, params: Record<string, string>) {
    setPhases((s) => ({ ...s, [phase]: { ...s[phase], params } }))
  }

  const PHASES = [
    { phase: 1, title: "Theme Research", description: "Score all seed themes by demand, competition, and monetisation" },
    { phase: 2, title: "Subject List Generation", description: "Generate 20 product subjects from a winning theme" },
    { phase: 3, title: "Image Generation", description: "Generate artwork + 3 mockups for a subject" },
    { phase: 4, title: "Packaging", description: "Create delivery ZIP + review PDF for a subject" },
    { phase: 5, title: "Human Review Notification", description: "Email + Slack alert — pauses for approval" },
    { phase: 6, title: "Etsy Draft Upload", description: "Upload approved subject as a draft listing" },
  ]

  return (
    <div className="space-y-4">
      <p className="text-sm font-body text-on-surface-variant">
        Trigger each phase individually. Phases 2–6 require a theme or subject slug from the previous phase output.
      </p>
      {PHASES.map(({ phase, title, description }) => (
        <PhaseCard
          key={phase}
          phase={phase}
          title={title}
          description={description}
          params={phases[phase].params}
          setParams={(p) => setParams(phase, p)}
          onTrigger={() => handleTrigger(phase)}
          isPending={pending[phase] ?? false}
          result={phases[phase].result}
          error={phases[phase].error}
        />
      ))}
    </div>
  )
}

function ListingsTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["etsyListings"],
    queryFn: fetchListings,
    refetchInterval: 30_000,
  })

  if (error) {
    return (
      <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label">
        Failed to load listings: {(error as Error).message}
      </div>
    )
  }

  const items = data?.items ?? []

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-container-low border-b border-outline-variant/10">
              {["Title", "Status", "Tags", "Price", "Created", "Actions"].map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/10">
            {isLoading
              ? Array(4).fill(null).map((_, i) => (
                  <tr key={i}>
                    {Array(6).fill(null).map((__, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 bg-surface-dim rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              : items.length > 0
              ? items.map((item: Record<string, unknown>, i: number) => (
                  <tr key={i} className="hover:bg-surface-container-low/40 transition-colors">
                    <td className="px-4 py-3 text-sm font-label text-on-surface max-w-[200px] truncate">
                      {(item.title as string) ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={item.status as string} />
                    </td>
                    <td className="px-4 py-3 text-xs font-label text-on-surface-variant">
                      {Array.isArray(item.tags) ? `${(item.tags as string[]).length} tags` : "—"}
                    </td>
                    <td className="px-4 py-3 text-sm font-label text-on-surface">
                      {item.price_usd ? `$${item.price_usd}` : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs font-label text-on-surface-variant">
                      {item.created_at
                        ? new Date(item.created_at as string).toLocaleDateString("en-US", { month: "short", day: "numeric" })
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      {item.drive_folder ? (
                        <a
                          href={String(item.drive_folder)}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-label font-semibold text-primary hover:underline"
                        >
                          Drive
                        </a>
                      ) : "—"}
                    </td>
                  </tr>
                ))
              : (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm font-label text-on-surface-variant">
                    No listings yet — run Phase 1 to start
                  </td>
                </tr>
              )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function EtsyVenture() {
  const [tab, setTab] = useState<Tab>("pipeline")

  const tabs: { id: Tab; label: string }[] = [
    { id: "pipeline", label: "Pipeline Control" },
    { id: "listings", label: "Listings" },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="material-symbols-outlined text-[24px] text-secondary">storefront</span>
            <h1 className="font-headline font-bold text-2xl text-on-surface">MiroPrintStudio — Etsy</h1>
          </div>
          <p className="text-sm font-body text-on-surface-variant">
            AI-generated digital wall art — 6-phase automated pipeline
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200">
          <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
          <span className="text-xs font-label font-medium text-amber-700">Etsy API key pending</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0.5 bg-surface-container-low p-1 rounded-xl w-fit">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-label font-medium transition-colors ${
              tab === t.id
                ? "bg-surface-container-lowest text-on-surface shadow-float"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "pipeline" && <PipelineTab />}
      {tab === "listings" && <ListingsTab />}
    </div>
  )
}
