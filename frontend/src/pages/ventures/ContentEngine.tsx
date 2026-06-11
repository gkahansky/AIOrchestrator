import { ReactNode, useEffect, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  ContentAsset,
  ContentBrand,
  ContentItem,
  ContentStrategy,
  SocialAccount,
  approveContentStrategy,
  createContentItem,
  createContentStrategy,
  createSocialAccount,
  fetchContentBrands,
  fetchContentItems,
  fetchContentStrategies,
  fetchCostDigest,
  fetchPublishJobs,
  fetchSocialAccounts,
  generateContentItem,
  patchContentBrand,
  patchContentStrategy,
  publishContentItemNow,
  regenerateBrandVoice,
  reviewContentItem,
  scheduleContentItem,
  seedEchoforgeBrand,
  startOAuth,
} from "../../api"

type Tab = "items" | "strategies" | "brands" | "accounts" | "publishes" | "cost"

const CHANNELS = ["linkedin_page", "facebook_page", "instagram_business", "youtube_channel"]
const FORMATS = ["post", "carousel", "reel", "short", "long_video", "blog", "newsletter"]
const PILLARS = [
  "WCAG how-to (a single criterion explained)",
  "Real failure deep-dive (an audit finding, anonymised)",
  "Regulatory update (ADA / EAA / Section 508 news)",
  "Mythbuster (a common accessibility misconception)",
  "Adjacent quality / UX / SEO crossover",
]
// Per-channel format allow-list (mirrors backend CHANNEL_FORMATS).
const CHANNEL_FORMATS: Record<string, string[]> = {
  linkedin_page:      ["post", "carousel", "long_video"],
  facebook_page:      ["post", "carousel", "reel"],
  instagram_business: ["post", "carousel", "reel"],
  youtube_channel:    ["short", "long_video"],
}

const STATUS_COLOR: Record<string, string> = {
  brief:          "bg-surface-container-high text-on-surface-variant",
  generating:     "bg-tertiary-fixed text-tertiary",
  review_pending: "bg-secondary-fixed text-secondary",
  revising:       "bg-secondary-fixed text-secondary",
  approved:       "bg-primary-fixed text-primary",
  scheduled:      "bg-primary-fixed text-primary",
  publishing:     "bg-tertiary-fixed text-tertiary",
  published:      "bg-green-100 text-green-800",
  failed:         "bg-error-container text-error",
  cancelled:      "bg-surface-container-high text-on-surface-variant",
}


export default function ContentEngine() {
  const [tab, setTab] = useState<Tab>("items")
  const [brandFilter, setBrandFilter] = useState<string | undefined>(undefined)
  const [oauthBanner, setOauthBanner] = useState<{ kind: "success" | "error"; detail: string } | null>(null)

  // Surface ?oauth=success|error redirects from the callback.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const oauth = params.get("oauth")
    if (oauth === "success") {
      setOauthBanner({ kind: "success", detail: "Account connected." })
      setTab("accounts")
    } else if (oauth === "error") {
      setOauthBanner({ kind: "error", detail: params.get("detail") || "Connection failed." })
      setTab("accounts")
    }
    if (oauth) {
      // Clean the URL so the toast doesn't reappear on refresh.
      const url = new URL(window.location.href)
      url.searchParams.delete("oauth")
      url.searchParams.delete("detail")
      window.history.replaceState({}, "", url.toString())
    }
  }, [])

  const { data: brands = [] } = useQuery({
    queryKey: ["ce", "brands"],
    queryFn: fetchContentBrands,
    refetchInterval: 30_000,
  })

  return (
    <div className="space-y-5">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-headline font-bold text-2xl text-on-surface">Content Engine</h1>
          <p className="text-sm font-body text-on-surface-variant mt-0.5">
            Multi-channel social content — drafted, reviewed, scheduled, published.
          </p>
        </div>
        <BrandPicker brands={brands} value={brandFilter} onChange={setBrandFilter} />
      </header>

      <nav className="flex gap-1 border-b border-outline-variant/20">
        {(["items", "strategies", "brands", "accounts", "publishes", "cost"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={[
              "px-4 py-2 text-sm font-label font-medium capitalize transition-colors",
              tab === t
                ? "text-primary border-b-2 border-primary"
                : "text-on-surface-variant hover:text-on-surface",
            ].join(" ")}
          >
            {t}
          </button>
        ))}
      </nav>

      {oauthBanner && (
        <div className={[
          "rounded-lg px-3 py-2 text-sm font-label flex items-center justify-between",
          oauthBanner.kind === "success"
            ? "bg-green-100 text-green-800"
            : "bg-error-container text-error",
        ].join(" ")}>
          <span>{oauthBanner.detail}</span>
          <button onClick={() => setOauthBanner(null)} className="text-xs font-bold">×</button>
        </div>
      )}

      {tab === "items"      && <ItemsTab brands={brands} brandFilter={brandFilter} />}
      {tab === "strategies" && <StrategiesTab brands={brands} brandFilter={brandFilter} />}
      {tab === "brands"     && <BrandsTab brands={brands} />}
      {tab === "accounts"   && <AccountsTab brands={brands} brandFilter={brandFilter} />}
      {tab === "publishes"  && <PublishesTab />}
      {tab === "cost"       && <CostTab brandFilter={brandFilter} />}
    </div>
  )
}


function BrandPicker({
  brands, value, onChange,
}: { brands: ContentBrand[]; value: string | undefined; onChange: (v: string | undefined) => void }) {
  if (brands.length === 0) return null
  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || undefined)}
      className="px-3 py-1.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30 text-sm font-body text-on-surface"
    >
      <option value="">All brands</option>
      {brands.map((b) => (
        <option key={b.id} value={b.id}>{b.name}</option>
      ))}
    </select>
  )
}


// ── Brands tab ─────────────────────────────────────────────────────────────────

function BrandsTab({ brands }: { brands: ContentBrand[] }) {
  const queryClient = useQueryClient()
  const seed = useMutation({
    mutationFn: seedEchoforgeBrand,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ce", "brands"] }),
  })

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-headline font-semibold text-base text-on-surface">Brands</h2>
        <button
          onClick={() => seed.mutate()}
          disabled={seed.isPending || brands.some((b) => b.slug === "echoforge_accessibility")}
          className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-sm font-label font-medium disabled:opacity-40"
        >
          {seed.isPending ? "Seeding…" : "Seed EchoForge Accessibility"}
        </button>
      </div>
      {brands.length === 0 ? (
        <p className="text-sm text-on-surface-variant">No brands yet. Seed EchoForge Accessibility to begin.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {brands.map((b) => <BrandCard key={b.id} brand={b} />)}
        </div>
      )}
    </section>
  )
}


function BrandCard({ brand }: { brand: ContentBrand }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [regenError, setRegenError] = useState<string | null>(null)

  const regen = useMutation({
    mutationFn: () => regenerateBrandVoice(brand.id),
    onSuccess: () => {
      setRegenError(null)
      queryClient.invalidateQueries({ queryKey: ["ce", "brands"] })
    },
    onError: (err: Error) => setRegenError(err.message),
  })

  return (
    <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="font-headline font-bold text-base text-on-surface">{brand.name}</div>
          <div className="text-xs font-label text-on-surface-variant">{brand.slug}</div>
        </div>
        <div className="flex flex-wrap gap-1 items-center">
          {brand.auto_strategy_enabled && (
            <span className="text-[10px] font-label font-bold uppercase tracking-wider bg-primary-fixed text-primary px-1.5 py-0.5 rounded">
              Auto-strategy
            </span>
          )}
          {brand.auto_approve_min_score > 0 && (
            <span className="text-[10px] font-label font-bold uppercase tracking-wider bg-green-100 text-green-800 px-1.5 py-0.5 rounded">
              Auto-approve ≥ {brand.auto_approve_min_score}
            </span>
          )}
          <button
            onClick={() => setEditing(true)}
            className="px-2 py-0.5 rounded-md bg-surface-container-high text-on-surface text-[11px] font-label font-medium"
          >
            Edit
          </button>
        </div>
      </div>
      {brand.description && (
        <p className="text-xs font-body text-on-surface-variant line-clamp-3 mb-2">{brand.description}</p>
      )}
      <div className="text-xs font-label text-on-surface-variant space-y-0.5">
        <div>Themes: {Object.entries(brand.theme_weights).map(([k, v]) => `${k} ${Math.round((v as number) * 100)}%`).join(" · ")}</div>
        <div>Personas: {brand.target_personas.length} · Banned phrases: {brand.banned_phrases.length}</div>
        <div>Cadence: {Object.entries(brand.channel_cadence).map(([c, n]) => `${c.split("_")[0]} ${n}/wk`).join(" · ")}</div>
      </div>

      {brand.banned_phrases.length > 0 && (
        <details className="mt-2 text-xs font-label">
          <summary className="cursor-pointer text-on-surface-variant hover:text-on-surface">
            Banned phrases ({brand.banned_phrases.length})
          </summary>
          <div className="flex flex-wrap gap-1 mt-1">
            {brand.banned_phrases.map((p, i) => (
              <span key={i} className="bg-error-container/40 text-error px-1.5 py-0.5 rounded text-[10px]">
                {p}
              </span>
            ))}
          </div>
        </details>
      )}

      <div className="mt-3 pt-3 border-t border-outline-variant/15 flex items-center justify-between gap-2">
        <div className="text-xs font-label text-on-surface-variant truncate">
          Voice sources: {brand.voice_source_urls.length
            ? brand.voice_source_urls.join(", ")
            : "(none configured)"}
        </div>
        <button
          onClick={() => regen.mutate()}
          disabled={brand.voice_source_urls.length === 0 || regen.isPending}
          className="px-2.5 py-1 rounded-md bg-surface-container-high text-on-surface text-xs font-label font-medium disabled:opacity-40 shrink-0"
        >
          {regen.isPending ? "Regenerating…" : "Regenerate voice"}
        </button>
      </div>
      {regenError && (
        <div className="text-[11px] font-label text-error mt-1">{regenError}</div>
      )}

      {editing && (
        <BrandEditModal brand={brand} onClose={() => setEditing(false)} />
      )}
    </div>
  )
}


function BrandEditModal({ brand, onClose }: { brand: ContentBrand; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(brand.name)
  const [description, setDescription] = useState(brand.description ?? "")
  const [autoApprove, setAutoApprove] = useState(brand.auto_approve_min_score)
  const [autoStrategy, setAutoStrategy] = useState(brand.auto_strategy_enabled)
  const [banned, setBanned] = useState<string[]>(brand.banned_phrases)
  const [bannedDraft, setBannedDraft] = useState("")
  const [sources, setSources] = useState<string[]>(brand.voice_source_urls)
  const [sourceDraft, setSourceDraft] = useState("")
  const [personas, setPersonas] = useState(JSON.stringify(brand.target_personas, null, 2))
  const [themeWeights, setThemeWeights] = useState(JSON.stringify(brand.theme_weights, null, 2))
  const [cadence, setCadence] = useState(JSON.stringify(brand.channel_cadence, null, 2))
  const [error, setError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: () => {
      let parsedPersonas, parsedThemes, parsedCadence
      try { parsedPersonas = JSON.parse(personas) } catch { throw new Error("Personas: invalid JSON") }
      try { parsedThemes = JSON.parse(themeWeights) } catch { throw new Error("Theme weights: invalid JSON") }
      try { parsedCadence = JSON.parse(cadence) } catch { throw new Error("Channel cadence: invalid JSON") }
      return patchContentBrand(brand.id, {
        name,
        description: description || null,
        auto_approve_min_score: autoApprove,
        auto_strategy_enabled: autoStrategy,
        banned_phrases: banned,
        voice_source_urls: sources,
        target_personas: parsedPersonas,
        theme_weights: parsedThemes,
        channel_cadence: parsedCadence,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ce", "brands"] })
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  function addBanned() {
    const v = bannedDraft.trim()
    if (v && !banned.includes(v)) setBanned([...banned, v])
    setBannedDraft("")
  }
  function addSource() {
    const v = sourceDraft.trim()
    if (v && !sources.includes(v)) setSources([...sources, v])
    setSourceDraft("")
  }

  return (
    <div className="fixed inset-0 z-50 bg-on-surface/40 flex items-center justify-center p-4"
         onClick={onClose}>
      <div className="bg-surface-container-lowest rounded-xl shadow-float w-full max-w-2xl max-h-[90vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-3 border-b border-outline-variant/20 flex items-center justify-between sticky top-0 bg-surface-container-lowest">
          <h3 className="font-headline font-bold text-base text-on-surface">Edit {brand.slug}</h3>
          <button onClick={onClose} className="text-xl font-bold text-on-surface-variant">×</button>
        </div>
        <div className="p-5 space-y-4">
          <Field label="Name">
            <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
          </Field>
          <Field label="Description">
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className={inputCls} />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Auto-approve threshold (0 = always review)">
              <input type="number" min={0} max={100} step={5}
                     value={autoApprove}
                     onChange={(e) => setAutoApprove(parseInt(e.target.value) || 0)}
                     className={inputCls} />
            </Field>
            <Field label="Auto-strategy">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={autoStrategy}
                       onChange={(e) => setAutoStrategy(e.target.checked)} />
                <span>Enable automatic calendar regeneration</span>
              </label>
            </Field>
          </div>

          <Field label="Banned phrases (substring match, case-insensitive)">
            <div className="flex flex-wrap gap-1 mb-1">
              {banned.map((p, i) => (
                <span key={i} className="bg-error-container/50 text-error px-2 py-0.5 rounded text-xs flex items-center gap-1">
                  {p}
                  <button onClick={() => setBanned(banned.filter((_, j) => j !== i))}
                          className="text-error font-bold">×</button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input value={bannedDraft} onChange={(e) => setBannedDraft(e.target.value)}
                     onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addBanned() } }}
                     placeholder="e.g. let's dive into"
                     className={inputCls} />
              <button onClick={addBanned} type="button"
                      className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface text-xs font-label">
                Add
              </button>
            </div>
          </Field>

          <Field label="Voice source URLs (re-scraped on 'Regenerate voice')">
            <div className="space-y-1 mb-1">
              {sources.map((u, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="flex-1 truncate text-on-surface">{u}</span>
                  <button onClick={() => setSources(sources.filter((_, j) => j !== i))}
                          className="text-error font-bold">×</button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <input value={sourceDraft} onChange={(e) => setSourceDraft(e.target.value)}
                     onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addSource() } }}
                     placeholder="https://echoforge.biz/services/..."
                     className={inputCls} />
              <button onClick={addSource} type="button"
                      className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface text-xs font-label">
                Add
              </button>
            </div>
          </Field>

          <Field label="Theme weights (JSON — values 0..1)">
            <textarea value={themeWeights} onChange={(e) => setThemeWeights(e.target.value)} rows={3}
                      className={`${inputCls} font-mono text-[11px]`} />
          </Field>
          <Field label="Channel cadence (JSON — posts per week per channel)">
            <textarea value={cadence} onChange={(e) => setCadence(e.target.value)} rows={5}
                      className={`${inputCls} font-mono text-[11px]`} />
          </Field>
          <Field label="Target personas (JSON list)">
            <textarea value={personas} onChange={(e) => setPersonas(e.target.value)} rows={6}
                      className={`${inputCls} font-mono text-[11px]`} />
          </Field>

          {error && <div className="text-xs font-label text-error">{error}</div>}

          <div className="flex justify-end gap-2 pt-2">
            <button onClick={onClose} type="button"
                    className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface text-sm font-label">
              Cancel
            </button>
            <button onClick={() => save.mutate()} disabled={save.isPending} type="button"
                    className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-sm font-label font-medium disabled:opacity-40">
              {save.isPending ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

const inputCls = "block w-full px-3 py-2 rounded-lg bg-surface-container-low text-on-surface text-sm"

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <div className="text-xs font-label text-on-surface-variant mb-1">{label}</div>
      {children}
    </label>
  )
}


// ── Strategies tab ─────────────────────────────────────────────────────────────

function StrategiesTab({ brands, brandFilter }: { brands: ContentBrand[]; brandFilter: string | undefined }) {
  const queryClient = useQueryClient()
  const [draftForm, setDraftForm] = useState<{ brandId: string } | null>(null)

  const { data: strategies = [], isLoading } = useQuery({
    queryKey: ["ce", "strategies", brandFilter ?? "all"],
    queryFn: () => fetchContentStrategies(brandFilter),
  })

  const approve = useMutation({
    mutationFn: approveContentStrategy,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ce", "strategies"] }),
  })

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-headline font-semibold text-base text-on-surface">Editorial Strategies</h2>
        <div className="flex gap-2 flex-wrap">
          {brands.map((b) => (
            <button
              key={b.id}
              onClick={() => setDraftForm({ brandId: b.id })}
              className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface text-sm font-label font-medium hover:bg-primary-fixed"
            >
              + Draft for {b.name}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-on-surface-variant">Loading…</p>
      ) : strategies.length === 0 ? (
        <p className="text-sm text-on-surface-variant">No strategies yet. Draft one above.</p>
      ) : (
        <div className="space-y-3">
          {strategies.map((s) => (
            <StrategyCard
              key={s.id}
              strategy={s}
              onApprove={() => approve.mutate(s.id)}
              approving={approve.isPending}
            />
          ))}
        </div>
      )}

      {draftForm && (
        <StrategyDraftForm
          brand={brands.find((b) => b.id === draftForm.brandId)!}
          onClose={() => setDraftForm(null)}
        />
      )}
    </section>
  )
}


function StrategyDraftForm({ brand, onClose }: { brand: ContentBrand; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [periodDays, setPeriodDays] = useState(30)
  const [title, setTitle] = useState("")
  const [userBrief, setUserBrief] = useState("")
  const [mustCover, setMustCover] = useState<string[]>([])
  const [mustCoverDraft, setMustCoverDraft] = useState("")
  const [events, setEvents] = useState<string[]>([])
  const [eventsDraft, setEventsDraft] = useState("")
  const [tone, setTone] = useState("")
  const [cadence, setCadence] = useState<Record<string, number>>({ ...brand.channel_cadence })

  const create = useMutation({
    mutationFn: () => createContentStrategy({
      brand_id: brand.id,
      period_days: periodDays,
      title: title || undefined,
      channel_cadence: cadence,
      user_brief: userBrief || undefined,
      must_cover_topics: mustCover.length ? mustCover : undefined,
      upcoming_events: events.length ? events : undefined,
      tone_notes: tone || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ce", "strategies"] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 z-50 bg-on-surface/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-surface-container-lowest rounded-xl shadow-float w-full max-w-2xl max-h-[90vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-3 border-b border-outline-variant/20 flex items-center justify-between sticky top-0 bg-surface-container-lowest">
          <h3 className="font-headline font-bold text-base text-on-surface">Draft strategy — {brand.name}</h3>
          <button onClick={onClose} className="text-xl font-bold text-on-surface-variant">×</button>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Period (days)">
              <input type="number" min={7} max={90} step={1}
                     value={periodDays}
                     onChange={(e) => setPeriodDays(parseInt(e.target.value) || 30)}
                     className={inputCls} />
            </Field>
            <Field label="Title (optional)">
              <input value={title} onChange={(e) => setTitle(e.target.value)}
                     placeholder={`${brand.name} — ${periodDays}-day calendar`}
                     className={inputCls} />
            </Field>
          </div>

          <Field label="Per-channel cadence (posts per week)">
            <div className="grid grid-cols-2 gap-2">
              {CHANNELS.map((c) => (
                <label key={c} className="flex items-center gap-2 text-xs">
                  <span className="flex-1 capitalize">{c.replace(/_/g, " ")}</span>
                  <input type="number" min={0} max={14} step={1}
                         value={cadence[c] ?? 0}
                         onChange={(e) => setCadence({ ...cadence, [c]: parseInt(e.target.value) || 0 })}
                         className="w-16 px-2 py-1 rounded-md bg-surface-container-low text-on-surface text-xs text-right" />
                </label>
              ))}
            </div>
          </Field>

          <Field label="Operator brief — what should the calendar focus on?">
            <textarea value={userBrief} onChange={(e) => setUserBrief(e.target.value)} rows={4}
                      placeholder="e.g. June is European Accessibility Month — front-load EAA content. Be warmer than last month."
                      className={inputCls} />
          </Field>

          <Field label="Must-cover topics">
            <ChipInput values={mustCover} setValues={setMustCover} draft={mustCoverDraft} setDraft={setMustCoverDraft}
                       placeholder="e.g. WCAG 2.5.3 Label in Name" />
          </Field>
          <Field label="Upcoming events / dates to weave in">
            <ChipInput values={events} setValues={setEvents} draft={eventsDraft} setDraft={setEventsDraft}
                       placeholder="e.g. GAAD May 16 — Global Accessibility Awareness Day" />
          </Field>
          <Field label="Tone notes">
            <textarea value={tone} onChange={(e) => setTone(e.target.value)} rows={2}
                      placeholder="e.g. less corporate, more direct. Lead with example, then rule."
                      className={inputCls} />
          </Field>

          {create.isError && (
            <div className="text-xs font-label text-error">{(create.error as Error).message}</div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button onClick={onClose} type="button"
                    className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface text-sm font-label">
              Cancel
            </button>
            <button onClick={() => create.mutate()} disabled={create.isPending} type="button"
                    className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-sm font-label font-medium disabled:opacity-40 flex items-center gap-2">
              {create.isPending && <Spinner size={14} />}
              {create.isPending ? "Drafting calendar…" : "Draft calendar"}
            </button>
          </div>
        </div>
      </div>

      {create.isPending && <FullPageSpinner label="Drafting calendar — Claude is enriching each slot…" />}
    </div>
  )
}


function ChipInput({
  values, setValues, draft, setDraft, placeholder,
}: { values: string[]; setValues: (v: string[]) => void; draft: string; setDraft: (v: string) => void; placeholder: string }) {
  function add() {
    const v = draft.trim()
    if (v && !values.includes(v)) setValues([...values, v])
    setDraft("")
  }
  return (
    <>
      <div className="flex flex-wrap gap-1 mb-1">
        {values.map((v, i) => (
          <span key={i} className="bg-primary-fixed text-primary px-2 py-0.5 rounded text-xs flex items-center gap-1">
            {v}
            <button onClick={() => setValues(values.filter((_, j) => j !== i))} className="font-bold">×</button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input value={draft} onChange={(e) => setDraft(e.target.value)}
               onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add() } }}
               placeholder={placeholder} className={inputCls} />
        <button onClick={add} type="button"
                className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface text-xs font-label">
          Add
        </button>
      </div>
    </>
  )
}


function Spinner({ size = 16 }: { size?: number }) {
  return (
    <span
      className="inline-block animate-spin rounded-full border-2 border-current border-t-transparent"
      style={{ width: size, height: size }}
    />
  )
}


function FullPageSpinner({ label }: { label: string }) {
  return (
    <div className="fixed inset-0 z-[60] bg-on-surface/50 flex flex-col items-center justify-center gap-3">
      <Spinner size={36} />
      <div className="text-sm font-label text-on-primary bg-primary/90 px-3 py-1.5 rounded-lg shadow-float">
        {label}
      </div>
    </div>
  )
}


type CalendarSlot = ContentStrategy["calendar"][number]


function StrategyCard({
  strategy, onApprove, approving,
}: { strategy: ContentStrategy; onApprove: () => void; approving: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)

  return (
    <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
      <div className="flex items-start justify-between">
        <div>
          <div className="font-headline font-bold text-base text-on-surface">{strategy.title}</div>
          <div className="text-xs font-label text-on-surface-variant mt-0.5">
            {strategy.period_days} days · {strategy.calendar.length} slots ·{" "}
            <span className={`px-1.5 py-0.5 rounded ${STATUS_COLOR[strategy.status] ?? ""}`}>
              {strategy.status}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setExpanded(!expanded); setEditing(false) }}
            className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface text-sm font-label font-medium"
          >
            {expanded ? "Hide calendar" : "View calendar"}
          </button>
          {expanded && !editing && strategy.status === "draft" && (
            <button
              onClick={() => setEditing(true)}
              className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface text-sm font-label font-medium"
            >
              Edit
            </button>
          )}
          {strategy.status === "draft" && (
            <button
              onClick={onApprove}
              disabled={approving}
              className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-sm font-label font-medium disabled:opacity-40"
            >
              Approve
            </button>
          )}
        </div>
      </div>

      {expanded && !editing && <ReadOnlyCalendar slots={strategy.calendar} />}
      {expanded && editing && (
        <EditableCalendar strategy={strategy} onDone={() => setEditing(false)} />
      )}
    </div>
  )
}


function ReadOnlyCalendar({ slots }: { slots: CalendarSlot[] }) {
  return (
    <div className="mt-3 max-h-96 overflow-y-auto text-xs">
      <div className="grid grid-cols-12 gap-2 px-2 py-1 font-label font-bold text-on-surface-variant border-b border-outline-variant/15 sticky top-0 bg-surface-container-lowest">
        <span className="col-span-2">Date</span>
        <span className="col-span-2">Channel</span>
        <span className="col-span-2">Format</span>
        <span className="col-span-2">Pillar</span>
        <span className="col-span-4">Topic / hook</span>
      </div>
      {slots.map((slot, i) => (
        <div key={i} className="grid grid-cols-12 gap-2 px-2 py-1 odd:bg-surface-container-low/40 rounded">
          <span className="col-span-2 text-on-surface-variant">{slot.date}</span>
          <span className="col-span-2 font-label">{slot.channel?.split("_")[0]}</span>
          <span className="col-span-2 font-label">{slot.format}</span>
          <span className="col-span-2 truncate text-on-surface-variant">{slot.pillar ?? ""}</span>
          <span className="col-span-4 text-on-surface truncate">
            {slot.topic || slot.hook || "—"}
          </span>
        </div>
      ))}
    </div>
  )
}


function EditableCalendar({ strategy, onDone }: { strategy: ContentStrategy; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [slots, setSlots] = useState<CalendarSlot[]>(
    [...strategy.calendar].map((s, i) => ({ ...s, index: s.index ?? i })),
  )
  const [error, setError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: () => patchContentStrategy(strategy.id, {
      calendar: slots.map((s, i) => ({ ...s, index: i })),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ce", "strategies"] })
      onDone()
    },
    onError: (err: Error) => setError(err.message),
  })

  function patchSlot(i: number, patch: Partial<CalendarSlot>) {
    const next = [...slots]
    next[i] = { ...next[i], ...patch }
    setSlots(next)
  }
  function removeSlot(i: number) {
    setSlots(slots.filter((_, j) => j !== i))
  }
  function addSlot() {
    const last = slots[slots.length - 1]
    const nextDate = last?.date
      ? new Date(new Date(last.date).getTime() + 86400000).toISOString().slice(0, 10)
      : new Date().toISOString().slice(0, 10)
    setSlots([...slots, {
      index:   slots.length,
      date:    nextDate,
      channel: "linkedin_page",
      format:  "post",
      pillar:  PILLARS[0],
      topic:   "",
      angle:   "",
      hook:    "",
    }])
  }

  return (
    <div className="mt-3 space-y-2">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-surface-container-lowest">
            <tr className="font-label font-bold text-on-surface-variant border-b border-outline-variant/20">
              <th className="px-2 py-1.5 text-left w-32">Date</th>
              <th className="px-2 py-1.5 text-left w-40">Channel</th>
              <th className="px-2 py-1.5 text-left w-32">Format</th>
              <th className="px-2 py-1.5 text-left w-56">Pillar</th>
              <th className="px-2 py-1.5 text-left">Topic</th>
              <th className="px-2 py-1.5 text-left">Hook</th>
              <th className="px-2 py-1.5 w-8" />
            </tr>
          </thead>
          <tbody>
            {slots.map((slot, i) => {
              const allowedFormats = slot.channel ? (CHANNEL_FORMATS[slot.channel] ?? FORMATS) : FORMATS
              const fmt = allowedFormats.includes(slot.format) ? slot.format : allowedFormats[0]
              return (
                <tr key={i} className="odd:bg-surface-container-low/40">
                  <td className="px-2 py-1">
                    <input type="date"
                           value={slot.date ?? ""}
                           onChange={(e) => patchSlot(i, { date: e.target.value })}
                           className="w-full px-1.5 py-0.5 rounded bg-surface-container-low text-on-surface text-xs" />
                  </td>
                  <td className="px-2 py-1">
                    <select value={slot.channel ?? "linkedin_page"}
                            onChange={(e) => patchSlot(i, { channel: e.target.value })}
                            className="w-full px-1.5 py-0.5 rounded bg-surface-container-low text-on-surface text-xs">
                      {CHANNELS.map((c) => (
                        <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-1">
                    <select value={fmt}
                            onChange={(e) => patchSlot(i, { format: e.target.value })}
                            className="w-full px-1.5 py-0.5 rounded bg-surface-container-low text-on-surface text-xs">
                      {allowedFormats.map((f) => <option key={f} value={f}>{f}</option>)}
                    </select>
                  </td>
                  <td className="px-2 py-1">
                    <select value={slot.pillar ?? ""}
                            onChange={(e) => patchSlot(i, { pillar: e.target.value })}
                            className="w-full px-1.5 py-0.5 rounded bg-surface-container-low text-on-surface text-xs">
                      <option value="">—</option>
                      {PILLARS.map((p) => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </td>
                  <td className="px-2 py-1">
                    <input value={slot.topic ?? ""}
                           onChange={(e) => patchSlot(i, { topic: e.target.value })}
                           placeholder="Specific angle…"
                           className="w-full px-1.5 py-0.5 rounded bg-surface-container-low text-on-surface text-xs" />
                  </td>
                  <td className="px-2 py-1">
                    <input value={slot.hook ?? ""}
                           onChange={(e) => patchSlot(i, { hook: e.target.value })}
                           placeholder="First line of the post…"
                           className="w-full px-1.5 py-0.5 rounded bg-surface-container-low text-on-surface text-xs" />
                  </td>
                  <td className="px-2 py-1">
                    <button onClick={() => removeSlot(i)} type="button"
                            className="text-error font-bold text-base">×</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-outline-variant/15">
        <button onClick={addSlot} type="button"
                className="px-2.5 py-1 rounded-md bg-surface-container-high text-on-surface text-xs font-label font-medium">
          + Add row
        </button>
        <div className="flex items-center gap-2">
          {error && <span className="text-[11px] font-label text-error">{error}</span>}
          <button onClick={onDone} type="button"
                  className="px-2.5 py-1 rounded-md bg-surface-container-high text-on-surface text-xs font-label">
            Cancel
          </button>
          <button onClick={() => save.mutate()} disabled={save.isPending} type="button"
                  className="px-2.5 py-1 rounded-md bg-primary text-on-primary text-xs font-label font-medium disabled:opacity-40 flex items-center gap-1">
            {save.isPending && <Spinner size={12} />}
            {save.isPending ? "Saving…" : "Save calendar"}
          </button>
        </div>
      </div>
    </div>
  )
}


// ── Items tab ──────────────────────────────────────────────────────────────────

function ItemsTab({ brands, brandFilter }: { brands: ContentBrand[]; brandFilter: string | undefined }) {
  const queryClient = useQueryClient()
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["ce", "items", brandFilter ?? "all"],
    queryFn: () => fetchContentItems({ brand_id: brandFilter }),
    refetchInterval: 10_000,
  })

  const [showCreate, setShowCreate] = useState(false)

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-headline font-semibold text-base text-on-surface">Content Items</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          disabled={brands.length === 0}
          className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-sm font-label font-medium disabled:opacity-40"
        >
          {showCreate ? "Cancel" : "+ New item"}
        </button>
      </div>

      {showCreate && <NewItemForm brands={brands} onCreated={() => {
        queryClient.invalidateQueries({ queryKey: ["ce", "items"] })
        setShowCreate(false)
      }} />}

      {isLoading ? (
        <p className="text-sm text-on-surface-variant">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-on-surface-variant">No items yet.</p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => <ItemRow key={item.id} item={item} />)}
        </div>
      )}
    </section>
  )
}


function NewItemForm({ brands, onCreated }: { brands: ContentBrand[]; onCreated: () => void }) {
  const queryClient = useQueryClient()
  const [brandId, setBrandId]   = useState(brands[0]?.id ?? "")
  const [topic, setTopic]       = useState("")
  const [format, setFormat]     = useState("post")
  const [channels, setChannels] = useState<string[]>(["linkedin_page"])

  const create = useMutation({
    mutationFn: () => createContentItem({
      brand_id: brandId, topic, format, channels, title: topic.slice(0, 80),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ce", "items"] })
      onCreated()
    },
  })

  return (
    <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <label className="text-xs font-label text-on-surface-variant">
          Brand
          <select
            value={brandId}
            onChange={(e) => setBrandId(e.target.value)}
            className="block w-full mt-1 px-3 py-2 rounded-lg bg-surface-container-low text-on-surface text-sm"
          >
            {brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
        <label className="text-xs font-label text-on-surface-variant">
          Format
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value)}
            className="block w-full mt-1 px-3 py-2 rounded-lg bg-surface-container-low text-on-surface text-sm"
          >
            {FORMATS.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </label>
      </div>
      <label className="block text-xs font-label text-on-surface-variant">
        Topic
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. WCAG 2.5.3 Label in Name — accordion buttons"
          className="block w-full mt-1 px-3 py-2 rounded-lg bg-surface-container-low text-on-surface text-sm"
        />
      </label>
      <fieldset className="text-xs font-label text-on-surface-variant">
        <legend>Channels</legend>
        <div className="flex gap-2 mt-1 flex-wrap">
          {CHANNELS.map((c) => (
            <label key={c} className={[
              "px-3 py-1.5 rounded-lg cursor-pointer text-xs font-label transition-colors border",
              channels.includes(c)
                ? "bg-primary-fixed text-primary border-primary"
                : "bg-surface-container-low text-on-surface-variant border-outline-variant/20",
            ].join(" ")}>
              <input
                type="checkbox"
                checked={channels.includes(c)}
                onChange={(e) => setChannels(e.target.checked
                  ? [...channels, c]
                  : channels.filter((x) => x !== c))}
                className="hidden"
              />
              {c.replace("_", " ")}
            </label>
          ))}
        </div>
      </fieldset>
      <button
        onClick={() => create.mutate()}
        disabled={!brandId || !topic.trim() || channels.length === 0 || create.isPending}
        className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-sm font-label font-medium disabled:opacity-40"
      >
        {create.isPending ? "Creating…" : "Create item"}
      </button>
    </div>
  )
}


function ItemRow({ item }: { item: ContentItem }) {
  const [expanded, setExpanded] = useState(false)
  const queryClient = useQueryClient()

  const generate = useMutation({
    mutationFn: () => generateContentItem(item.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ce", "items"] }),
  })
  const review = useMutation({
    mutationFn: (action: "approve" | "revise" | "reject") => reviewContentItem(item.id, action),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ce", "items"] }),
  })
  const schedule = useMutation({
    mutationFn: (when: string) => scheduleContentItem(item.id, when),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ce", "items"] }),
  })
  const publishNow = useMutation({
    mutationFn: () => publishContentItemNow(item.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ce", "items"] }),
  })

  const variants = Object.entries(item.variants_json ?? {})

  return (
    <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`text-[10px] font-label font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${STATUS_COLOR[item.status] ?? ""}`}>
              {item.status}
            </span>
            <span className="text-xs font-label text-on-surface-variant">
              {item.format} · {item.channels.join(", ")}
            </span>
            <span
              className={[
                "text-[10px] font-label font-bold uppercase px-1.5 py-0.5 rounded",
                item.asset_count > 0
                  ? "bg-primary-fixed text-primary"
                  : "bg-surface-container-high text-on-surface-variant",
              ].join(" ")}
              title={`${item.asset_count} media asset(s) — image / video files attached to this item`}
            >
              {item.asset_count} media
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation()
                navigator.clipboard.writeText(item.id)
              }}
              className="text-[10px] font-mono text-on-surface-variant hover:text-primary cursor-pointer"
              title="Click to copy item ID"
            >
              id:{item.id.slice(0, 8)}
            </button>
          </div>
          <div className="font-body text-sm text-on-surface line-clamp-2">
            {item.title || item.topic || "(no title)"}
          </div>
          {item.scheduled_for && (
            <div className="text-xs font-label text-on-surface-variant mt-0.5">
              Scheduled for {new Date(item.scheduled_for).toLocaleString()}
            </div>
          )}
        </div>
        <div className="flex gap-1 flex-wrap justify-end">
          {item.status === "brief" && (
            <button onClick={() => generate.mutate()} disabled={generate.isPending}
              className="px-2.5 py-1 rounded-md bg-primary text-on-primary text-xs font-label font-medium">
              Generate
            </button>
          )}
          {item.status === "review_pending" && (
            <>
              <button onClick={() => review.mutate("revise")}
                className="px-2.5 py-1 rounded-md bg-surface-container-high text-on-surface text-xs font-label font-medium">
                Revise
              </button>
              <button onClick={() => review.mutate("reject")}
                className="px-2.5 py-1 rounded-md bg-surface-container-high text-on-surface text-xs font-label font-medium">
                Reject
              </button>
              <button onClick={() => review.mutate("approve")}
                className="px-2.5 py-1 rounded-md bg-primary text-on-primary text-xs font-label font-medium">
                Approve
              </button>
            </>
          )}
          {item.status === "approved" && (
            <>
              <button
                onClick={() => {
                  const when = prompt("Schedule for (ISO datetime, e.g. 2026-06-01T09:00:00Z)")
                  if (when) schedule.mutate(when)
                }}
                className="px-2.5 py-1 rounded-md bg-surface-container-high text-on-surface text-xs font-label font-medium">
                Schedule
              </button>
              <button onClick={() => publishNow.mutate()}
                className="px-2.5 py-1 rounded-md bg-primary text-on-primary text-xs font-label font-medium">
                Publish now
              </button>
            </>
          )}
          <button onClick={() => setExpanded(!expanded)}
            className="px-2.5 py-1 rounded-md bg-surface-container-high text-on-surface-variant text-xs font-label">
            {expanded ? "Hide" : "Details"}
          </button>
        </div>
      </div>
      {expanded && (
        <div className="mt-3 pt-3 border-t border-outline-variant/15 space-y-3">
          {item.error_message && (
            <div className="text-xs font-body text-error bg-error-container/30 px-2 py-1 rounded whitespace-pre-wrap">
              {item.error_message}
            </div>
          )}

          <AssetsPanel assets={item.assets ?? []} />

          {variants.length === 0 ? (
            <p className="text-xs font-body text-on-surface-variant">No generated variants yet.</p>
          ) : (
            variants.map(([channel, v]) => (
              <div key={channel} className="space-y-1">
                <div className="text-xs font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                  {channel.replace("_", " ")}
                </div>
                <div className="text-xs font-body text-on-surface whitespace-pre-wrap bg-surface-container-low/40 px-2 py-1.5 rounded">
                  {v?.body || "(empty)"}
                </div>
              </div>
            ))
          )}
          {item.quality_report_json?.ai_tell_score != null && (
            <div className="text-xs font-label text-on-surface-variant">
              AI-tell score: {String(item.quality_report_json.ai_tell_score)} / 100
            </div>
          )}
        </div>
      )}
    </div>
  )
}


function AssetsPanel({ assets }: { assets: ContentAsset[] }) {
  if (assets.length === 0) {
    return (
      <p className="text-xs font-body text-on-surface-variant italic">
        No media assets yet — text-only item, or generation hasn't produced media (check error_message).
      </p>
    )
  }
  return (
    <div className="space-y-2">
      <div className="text-xs font-label font-semibold uppercase tracking-wider text-on-surface-variant">
        Generated media ({assets.length})
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {assets.map((a) => <AssetCard key={a.id} asset={a} />)}
      </div>
    </div>
  )
}


function AssetCard({ asset }: { asset: ContentAsset }) {
  const isVideo = asset.kind === "video"
  const isImage = asset.kind === "image" || asset.kind === "thumbnail"
  return (
    <div className="bg-surface-container-low/40 rounded-lg p-2 space-y-1.5">
      <div className="flex items-center justify-between text-[11px] font-label text-on-surface-variant">
        <span className="font-semibold uppercase">
          {asset.kind} {asset.role && <span className="opacity-70">· {asset.role}</span>}
        </span>
        <a href={asset.file_url} target="_blank" rel="noreferrer"
           className="text-primary hover:underline">
          Open ↗
        </a>
      </div>
      {isVideo && (
        <video src={asset.file_url} controls preload="metadata"
               className="w-full rounded-md bg-black" />
      )}
      {isImage && (
        <a href={asset.file_url} target="_blank" rel="noreferrer">
          <img src={asset.file_url} alt={asset.role || asset.kind}
               className="w-full rounded-md object-cover max-h-64" />
        </a>
      )}
      {!isVideo && !isImage && (
        <a href={asset.file_url} target="_blank" rel="noreferrer"
           className="block px-2 py-1.5 rounded-md bg-surface-container-high text-xs font-label text-center">
          Download {asset.kind}
        </a>
      )}
      {asset.cost_usd != null && asset.cost_usd > 0 && (
        <div className="text-[10px] font-label text-on-surface-variant text-right">
          ${asset.cost_usd.toFixed(4)}
        </div>
      )}
    </div>
  )
}


// ── Accounts tab ───────────────────────────────────────────────────────────────

const OAUTH_PROVIDERS: { id: "linkedin" | "meta" | "youtube"; label: string; covers: string[] }[] = [
  { id: "linkedin", label: "Connect LinkedIn Page",                covers: ["linkedin_page"] },
  { id: "meta",     label: "Connect Facebook + Instagram",         covers: ["facebook_page", "instagram_business"] },
  { id: "youtube",  label: "Connect YouTube Channel",              covers: ["youtube_channel"] },
]

function AccountsTab({ brands, brandFilter }: { brands: ContentBrand[]; brandFilter: string | undefined }) {
  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ["ce", "accounts", brandFilter ?? "all"],
    queryFn: () => fetchSocialAccounts(brandFilter),
    refetchInterval: 15_000,
  })

  const [connecting, setConnecting] = useState<string | null>(null)
  const [manualAdd, setManualAdd] = useState<{ brandId: string } | null>(null)

  async function handleConnect(provider: "linkedin" | "meta" | "youtube", brandId: string) {
    setConnecting(`${brandId}:${provider}`)
    try {
      const { auth_url } = await startOAuth(provider, brandId)
      window.location.href = auth_url
    } catch (err) {
      setConnecting(null)
      alert(`Connect failed: ${(err as Error).message}`)
    }
  }

  const visibleBrands = brandFilter ? brands.filter((b) => b.id === brandFilter) : brands

  return (
    <section className="space-y-5">
      <div>
        <h2 className="font-headline font-semibold text-base text-on-surface">Social Accounts</h2>
        <p className="text-xs font-body text-on-surface-variant mt-0.5">
          Each (brand × platform × account) is one row. Connect via OAuth, or paste a token manually
          for accounts the OAuth flow doesn't cover yet. Multiple accounts per channel are supported.
        </p>
      </div>

      {visibleBrands.length === 0 ? (
        <p className="text-sm text-on-surface-variant">Seed a brand first.</p>
      ) : (
        visibleBrands.map((b) => {
          const brandAccounts = accounts.filter((a) => a.brand_id === b.id)
          // Group by platform so users can see "2 LinkedIn pages connected" cleanly.
          const grouped = brandAccounts.reduce<Record<string, SocialAccount[]>>((acc, a) => {
            (acc[a.platform] = acc[a.platform] || []).push(a)
            return acc
          }, {})

          return (
            <div key={b.id} className="bg-surface-container-lowest rounded-xl p-4 shadow-float space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-headline font-bold text-base text-on-surface">{b.name}</div>
                  <div className="text-xs font-label text-on-surface-variant">
                    {brandAccounts.filter((a) => a.has_token).length} connected ·{" "}
                    {brandAccounts.length - brandAccounts.filter((a) => a.has_token).length} assisted-only
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {OAUTH_PROVIDERS.map((p) => {
                    const key = `${b.id}:${p.id}`
                    return (
                      <button
                        key={p.id}
                        onClick={() => handleConnect(p.id, b.id)}
                        disabled={connecting === key}
                        className={[
                          "px-3 py-1.5 rounded-lg text-xs font-label font-medium",
                          "bg-primary text-on-primary",
                          connecting === key ? "opacity-50" : "",
                        ].join(" ")}
                      >
                        {connecting === key ? "Redirecting…" : p.label}
                      </button>
                    )
                  })}
                  <button
                    onClick={() => setManualAdd({ brandId: b.id })}
                    className="px-3 py-1.5 rounded-lg text-xs font-label font-medium bg-surface-container-high text-on-surface"
                  >
                    + Add manually
                  </button>
                </div>
              </div>

              {CHANNELS.map((channel) => {
                const items = grouped[channel] ?? []
                return (
                  <div key={channel} className="pt-2 border-t border-outline-variant/15">
                    <div className="text-[11px] font-label font-bold uppercase tracking-wider text-on-surface-variant mb-1">
                      {channel.replace(/_/g, " ")} {items.length > 0 && <span>({items.length})</span>}
                    </div>
                    {items.length === 0 ? (
                      <div className="text-xs font-label text-on-surface-variant/70 italic">
                        No account connected — will fall back to assisted-send.
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {items.map((a) => (
                          <div key={a.id} className="bg-surface-container-low/40 rounded-lg p-2.5">
                            <div className="flex items-center justify-between mb-0.5">
                              <span className="font-headline font-semibold text-xs text-on-surface truncate">
                                {a.account_name || a.account_id || "(unnamed)"}
                              </span>
                              <span className={`text-[9px] font-label font-bold uppercase px-1.5 py-0.5 rounded ${
                                a.has_token
                                  ? "bg-green-100 text-green-800"
                                  : "bg-secondary-fixed text-secondary"
                              }`}>
                                {a.has_token ? "Connected" : "Assisted"}
                              </span>
                            </div>
                            <div className="text-[11px] font-label text-on-surface-variant">
                              {a.account_id && <span>ID: {a.account_id}</span>}
                              {a.expires_at && (
                                <span className="ml-2">expires {new Date(a.expires_at).toLocaleDateString()}</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )
        })
      )}

      {isLoading && <p className="text-xs text-on-surface-variant">Refreshing…</p>}

      {manualAdd && (
        <ManualAccountForm
          brand={brands.find((b) => b.id === manualAdd.brandId)!}
          onClose={() => setManualAdd(null)}
        />
      )}
    </section>
  )
}


function ManualAccountForm({ brand, onClose }: { brand: ContentBrand; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [platform, setPlatform] = useState(CHANNELS[0])
  const [accountId, setAccountId] = useState("")
  const [accountName, setAccountName] = useState("")
  const [token, setToken] = useState("")
  const [error, setError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () => createSocialAccount({
      brand_id: brand.id,
      platform,
      account_id: accountId || undefined,
      account_name: accountName || undefined,
      access_token: token || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ce", "accounts"] })
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  const hints: Record<string, string> = {
    linkedin_page:      "account_id must be the Page URN, e.g. urn:li:organization:12345",
    facebook_page:      "account_id is the Page ID (numeric)",
    instagram_business: "account_id is the IG user ID (NOT the Page ID); token = the linked Page token",
    youtube_channel:    "account_id is the channel ID (e.g. UCxxxx)",
  }

  return (
    <div className="fixed inset-0 z-50 bg-on-surface/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-surface-container-lowest rounded-xl shadow-float w-full max-w-lg max-h-[90vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-3 border-b border-outline-variant/20 flex items-center justify-between sticky top-0 bg-surface-container-lowest">
          <h3 className="font-headline font-bold text-base text-on-surface">Add account — {brand.name}</h3>
          <button onClick={onClose} className="text-xl font-bold text-on-surface-variant">×</button>
        </div>
        <div className="p-5 space-y-3">
          <Field label="Platform">
            <select value={platform} onChange={(e) => setPlatform(e.target.value)} className={inputCls}>
              {CHANNELS.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
            </select>
          </Field>
          <Field label="Account ID">
            <input value={accountId} onChange={(e) => setAccountId(e.target.value)}
                   placeholder={hints[platform]} className={inputCls} />
          </Field>
          <Field label="Account name (display only)">
            <input value={accountName} onChange={(e) => setAccountName(e.target.value)}
                   placeholder="e.g. EchoForge Accessibility" className={inputCls} />
          </Field>
          <Field label="Access token">
            <textarea value={token} onChange={(e) => setToken(e.target.value)} rows={3}
                      placeholder="Paste the OAuth access token here. Leave blank for assisted-send only."
                      className={`${inputCls} font-mono text-[11px]`} />
          </Field>

          {error && <div className="text-xs font-label text-error">{error}</div>}

          <div className="flex justify-end gap-2 pt-2">
            <button onClick={onClose} type="button"
                    className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface text-sm font-label">
              Cancel
            </button>
            <button onClick={() => create.mutate()} disabled={create.isPending || !accountId} type="button"
                    className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-sm font-label font-medium disabled:opacity-40">
              {create.isPending ? "Saving…" : "Save account"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}


// ── Publishes tab ──────────────────────────────────────────────────────────────

function PublishesTab() {
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ["ce", "publish-jobs"],
    queryFn: () => fetchPublishJobs(),
    refetchInterval: 15_000,
  })

  return (
    <section className="space-y-4">
      <h2 className="font-headline font-semibold text-base text-on-surface">Publish Log</h2>
      {isLoading ? (
        <p className="text-sm text-on-surface-variant">Loading…</p>
      ) : jobs.length === 0 ? (
        <p className="text-sm text-on-surface-variant">No publishes yet.</p>
      ) : (
        <div className="space-y-1">
          {jobs.map((j) => (
            <div key={j.id} className="grid grid-cols-12 gap-2 bg-surface-container-lowest rounded-lg px-3 py-2 text-xs font-body">
              <span className="col-span-2 font-label text-on-surface-variant">
                {new Date(j.created_at).toLocaleString()}
              </span>
              <span className="col-span-2 font-label">{j.channel.replace("_", " ")}</span>
              <span className="col-span-2">
                <span className={`text-[10px] font-label font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${STATUS_COLOR[j.status] ?? "bg-surface-container-high text-on-surface-variant"}`}>
                  {j.status}
                </span>
              </span>
              <span className="col-span-5 truncate text-on-surface">
                {j.external_url ? (
                  <a href={j.external_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                    {j.external_url}
                  </a>
                ) : j.deep_link ? (
                  <a href={j.deep_link} target="_blank" rel="noreferrer" className="text-secondary hover:underline">
                    open to post manually →
                  </a>
                ) : j.error_message || "—"}
              </span>
              <span className="col-span-1 font-label text-on-surface-variant text-right">
                {j.published_at ? "✓" : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}


// ── Cost tab ───────────────────────────────────────────────────────────────────

function CostTab({ brandFilter }: { brandFilter: string | undefined }) {
  const [days, setDays] = useState(7)
  const { data: rows = [], isLoading } = useQuery({
    queryKey: ["ce", "cost-digest", brandFilter ?? "all", days],
    queryFn: () => fetchCostDigest(brandFilter, days),
    refetchInterval: 60_000,
  })

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-headline font-semibold text-base text-on-surface">Cost-per-published-post</h2>
          <p className="text-xs font-body text-on-surface-variant mt-0.5">
            Same payload the weekly digest email computes. Pick a window — defaults to 7 days.
          </p>
        </div>
        <select value={days} onChange={(e) => setDays(parseInt(e.target.value))}
                className="px-3 py-1.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30 text-sm font-body text-on-surface">
          {[7, 14, 30, 60, 90].map((d) => <option key={d} value={d}>Last {d} days</option>)}
        </select>
      </div>

      {isLoading ? (
        <p className="text-sm text-on-surface-variant">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-on-surface-variant">No brands to report on.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="font-label font-bold text-on-surface-variant border-b border-outline-variant/20">
                <th className="px-2 py-2 text-left">Brand</th>
                <th className="px-2 py-2 text-right">Items published</th>
                <th className="px-2 py-2 text-right">Publish events</th>
                <th className="px-2 py-2 text-right">Total cost (USD)</th>
                <th className="px-2 py-2 text-right">Cost / post (USD)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.brand_id} className="odd:bg-surface-container-low/40">
                  <td className="px-2 py-2 font-headline font-semibold text-on-surface">{r.brand_name}</td>
                  <td className="px-2 py-2 text-right">{r.items_published}</td>
                  <td className="px-2 py-2 text-right">{r.publish_events}</td>
                  <td className="px-2 py-2 text-right tabular-nums">${r.total_cost_usd.toFixed(4)}</td>
                  <td className="px-2 py-2 text-right tabular-nums">${r.cost_per_post_usd.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <details className="text-xs font-label text-on-surface-variant">
        <summary className="cursor-pointer hover:text-on-surface">Where this comes from</summary>
        <ul className="mt-1 space-y-0.5 pl-4 list-disc">
          <li>"Items published" — count of <code>content_items</code> with <code>published_at</code> in the window.</li>
          <li>"Publish events" — successful <code>publish_jobs</code> rows in the window (one per channel × item).</li>
          <li>"Total cost" — sum of <code>content_assets.cost_usd</code> for published items.</li>
          <li>"Cost / post" — total cost ÷ publish events. So a single item that hit 3 channels divides the cost across 3.</li>
          <li>The weekly beat (<code>content.run_weekly_cost_digest</code>) emails the same numbers via Resend to <code>CONTENT_ENGINE_DIGEST_TO</code> (or <code>ALLOWED_EMAIL</code> as fallback).</li>
        </ul>
      </details>
    </section>
  )
}
