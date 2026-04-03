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

async function fetchThemes() {
  const res = await fetch(`${BASE}/api/ventures/etsy/themes`, { headers: getHeaders() })
  if (!res.ok) throw new Error("Failed to load themes")
  return res.json()
}

async function fetchSubjects() {
  const res = await fetch(`${BASE}/api/ventures/etsy/subjects`, { headers: getHeaders() })
  if (!res.ok) throw new Error("Failed to load subjects")
  return res.json()
}

interface Theme {
  theme: string
  score: number | null
  proceed: boolean
}

interface Subject {
  subject_id: string
  title_draft: string
  quality_tier: string
  price_usd: number
  subject: Record<string, unknown>
}


function PipelineTab() {
  const qc = useQueryClient()

  const { data: themesData } = useQuery({
    queryKey: ["etsyThemes"],
    queryFn: fetchThemes,
  })
  const themes: Theme[] = themesData?.themes ?? []
  // Show all themes sorted by score; mark passing ones but don't hide others
  const sortedThemes = [...themes].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))

  const { data: subjectsData, refetch: refetchSubjects } = useQuery({
    queryKey: ["etsySubjects"],
    queryFn: fetchSubjects,
  })
  const subjects: Subject[] = subjectsData?.subjects ?? []

  const [selectedSubject3, setSelectedSubject3] = useState<Subject | null>(null)
  const [selectedSubject4, setSelectedSubject4] = useState<Subject | null>(null)
  const [testPending, setTestPending] = useState<Record<number, boolean>>({})
  const [testResult, setTestResult] = useState<Record<number, string | null>>({})
  const [testError, setTestError] = useState<Record<number, string | null>>({})

  type PhaseState = { params: Record<string, string>; result: Record<string, unknown> | null; error: string | null }
  const [phases, setPhases] = useState<Record<number, PhaseState>>({
    1: { params: {}, result: null, error: null },
    2: { params: { theme: "" }, result: null, error: null },
  })
  const [pending, setPending] = useState<Record<number, boolean>>({})

  async function handleTrigger(phase: number) {
    setPending((p) => ({ ...p, [phase]: true }))
    setPhases((s) => ({ ...s, [phase]: { ...s[phase], error: null, result: null } }))
    try {
      const rawParams = phases[phase].params
      const cleanParams = Object.fromEntries(
        Object.entries(rawParams).filter(([, v]) => v.trim() !== "")
      )
      const result = await triggerPhase(phase, cleanParams)
      setPhases((s) => ({ ...s, [phase]: { ...s[phase], result } }))
      void qc.invalidateQueries({ queryKey: ["etsyListings"] })
      if (phase === 1) void qc.invalidateQueries({ queryKey: ["etsyThemes"] })
    } catch (e) {
      setPhases((s) => ({ ...s, [phase]: { ...s[phase], error: (e as Error).message } }))
    } finally {
      setPending((p) => ({ ...p, [phase]: false }))
    }
  }

  function setParams(phase: number, params: Record<string, string>) {
    setPhases((s) => ({ ...s, [phase]: { ...s[phase], params } }))
  }

  async function handleTestPhase(phase: number, subject: Subject | null) {
    if (!subject) return
    setTestPending((p) => ({ ...p, [phase]: true }))
    setTestResult((r) => ({ ...r, [phase]: null }))
    setTestError((e) => ({ ...e, [phase]: null }))
    try {
      const result = await triggerPhase(phase, { subject: subject.subject })
      setTestResult((r) => ({ ...r, [phase]: result.celery_task_id ?? result.job_id ?? "queued" }))
      void qc.invalidateQueries({ queryKey: ["etsyListings"] })
      if (phase === 2) void refetchSubjects()
    } catch (e) {
      setTestError((err) => ({ ...err, [phase]: (e as Error).message }))
    } finally {
      setTestPending((p) => ({ ...p, [phase]: false }))
    }
  }

  const PHASES = [
    { phase: 1, title: "Theme Research", description: "Score all seed themes by demand, competition, and monetisation" },
    { phase: 2, title: "Start Pipeline", description: "Select a theme → automatically runs image generation, packaging, and sends for human review" },
  ]

  return (
    <div className="space-y-4">
      <p className="text-sm font-body text-on-surface-variant">
        Run Phase 1 once to score themes. Then select a theme to start the full pipeline — subjects → images → packaging → human review → Etsy upload runs automatically.
      </p>
      {PHASES.map(({ phase, title, description }) => (
        <div key={phase} className="bg-surface-container-lowest rounded-xl p-5 shadow-float space-y-4">
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
              onClick={() => handleTrigger(phase)}
              disabled={pending[phase] ?? false}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-label font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 shrink-0"
            >
              {pending[phase] ? (
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

          {/* Phase 2 — theme dropdown */}
          {phase === 2 && (
            <div>
              <label className="block text-[10px] font-label font-medium uppercase tracking-wider text-on-surface-variant mb-1">
                Theme
              </label>
              {sortedThemes.length > 0 ? (
                <select
                  value={phases[2].params.theme}
                  onChange={(e) => setParams(2, { theme: e.target.value })}
                  className="w-full px-3 py-1.5 text-xs font-label bg-surface-container-low rounded-lg border border-transparent focus:border-primary/40 focus:outline-none text-on-surface"
                >
                  <option value="">— select a theme —</option>
                  {sortedThemes.map((t) => (
                    <option key={t.theme} value={t.theme}>
                      {t.theme}
                      {t.score != null ? ` (score: ${Math.round(t.score)})` : ""}
                      {t.proceed ? " ✓" : ""}
                    </option>
                  ))}
                </select>
              ) : (
                <p className="text-xs font-label text-on-surface-variant bg-surface-container-low px-3 py-2 rounded-lg">
                  No Phase 1 results found. Run Phase 1 first.
                </p>
              )}
            </div>
          )}


          {phases[phase].error && (
            <p className="text-xs font-label text-error bg-error-container px-3 py-2 rounded-lg">{phases[phase].error}</p>
          )}

          {phases[phase].result && (
            <div className="bg-surface-container-low rounded-lg px-3 py-2">
              <p className="text-[10px] font-label font-semibold uppercase tracking-wider text-on-surface-variant mb-1">Result</p>
              <p className="text-xs font-mono text-on-surface-variant break-all">
                {phase === 2
                  ? "Subjects queued — image generation will start automatically for each subject"
                  : `Task queued — celery_task_id: ${(phases[phase].result!.celery_task_id ?? phases[phase].result!.job_id) as string ?? "—"}`}
              </p>
            </div>
          )}
        </div>
      ))}

      {/* ── Test section ── */}
      {subjects.length > 0 && (
        <div className="border-t border-outline-variant/20 pt-4 space-y-3">
          <p className="text-xs font-label font-semibold uppercase tracking-wider text-on-surface-variant">
            Test individual subject
          </p>

          {/* Phase 3 test */}
          {[
            { phase: 3, label: "Image Generation", selected: selectedSubject3, setSelected: setSelectedSubject3 },
            { phase: 4, label: "Packaging", selected: selectedSubject4, setSelected: setSelectedSubject4 },
          ].map(({ phase, label, selected, setSelected }) => (
            <div key={phase} className="bg-surface-container-low rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-secondary-container flex items-center justify-center text-[10px] font-bold text-on-secondary-container">{phase}</span>
                  <span className="text-xs font-label font-semibold text-on-surface">{label} — single subject test</span>
                </div>
                <button
                  onClick={() => handleTestPhase(phase, selected)}
                  disabled={(testPending[phase] ?? false) || !selected}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-secondary text-on-secondary text-xs font-label font-semibold hover:opacity-90 transition-opacity disabled:opacity-40 shrink-0"
                >
                  {testPending[phase] ? (
                    <><div className="w-3 h-3 border border-on-secondary border-t-transparent rounded-full animate-spin" />Running…</>
                  ) : (
                    <><span className="material-symbols-outlined text-[14px]">science</span>Test</>
                  )}
                </button>
              </div>
              <select
                value={selected?.subject_id ?? ""}
                onChange={(e) => setSelected(subjects.find((s) => s.subject_id === e.target.value) ?? null)}
                className="w-full px-3 py-1.5 text-xs font-label bg-surface-container-lowest rounded-lg border border-transparent focus:border-primary/40 focus:outline-none text-on-surface"
              >
                <option value="">— select a subject —</option>
                {subjects.map((s) => (
                  <option key={s.subject_id} value={s.subject_id}>
                    {s.title_draft ?? s.subject_id}
                  </option>
                ))}
              </select>
              {testError[phase] && <p className="text-xs text-error">{testError[phase]}</p>}
              {testResult[phase] && <p className="text-xs font-mono text-on-surface-variant">Queued — task: {testResult[phase]}</p>}
            </div>
          ))}
        </div>
      )}
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
