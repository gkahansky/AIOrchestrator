import { useEffect, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  ContentBrand,
  ContentItem,
  ContentStrategy,
  approveContentStrategy,
  createContentItem,
  createContentStrategy,
  fetchContentBrands,
  fetchContentItems,
  fetchContentStrategies,
  fetchPublishJobs,
  fetchSocialAccounts,
  generateContentItem,
  patchContentBrand,
  publishContentItemNow,
  regenerateBrandVoice,
  reviewContentItem,
  scheduleContentItem,
  seedEchoforgeBrand,
  startOAuth,
} from "../../api"

type Tab = "items" | "strategies" | "brands" | "accounts" | "publishes"

const CHANNELS = ["linkedin_page", "facebook_page", "instagram_business", "youtube_channel"]
const FORMATS = ["post", "carousel", "reel", "short", "long_video", "blog", "newsletter"]

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
        {(["items", "strategies", "brands", "accounts", "publishes"] as Tab[]).map((t) => (
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
  const [threshold, setThreshold] = useState<number>(brand.auto_approve_min_score)
  const [thresholdDirty, setThresholdDirty] = useState(false)
  const [regenError, setRegenError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: (score: number) =>
      patchContentBrand(brand.id, { auto_approve_min_score: score }),
    onSuccess: () => {
      setThresholdDirty(false)
      queryClient.invalidateQueries({ queryKey: ["ce", "brands"] })
    },
  })

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
        <div className="flex gap-1">
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

      <div className="mt-3 pt-3 border-t border-outline-variant/15 space-y-2">
        <div className="flex items-center gap-2">
          <label className="text-xs font-label text-on-surface-variant flex-1">
            Auto-approve threshold (0 = always review)
          </label>
          <input
            type="number" min={0} max={100} step={5}
            value={threshold}
            onChange={(e) => { setThreshold(parseInt(e.target.value) || 0); setThresholdDirty(true) }}
            className="w-16 px-2 py-1 rounded-md bg-surface-container-low text-on-surface text-xs text-right"
          />
          <button
            onClick={() => save.mutate(threshold)}
            disabled={!thresholdDirty || save.isPending}
            className="px-2.5 py-1 rounded-md bg-primary text-on-primary text-xs font-label font-medium disabled:opacity-40"
          >
            {save.isPending ? "Saving…" : "Save"}
          </button>
        </div>

        <div className="flex items-center justify-between gap-2">
          <div className="text-xs font-label text-on-surface-variant truncate">
            Voice sources: {brand.voice_source_urls.length
              ? brand.voice_source_urls.join(", ")
              : "(none configured)"}
          </div>
          <button
            onClick={() => regen.mutate()}
            disabled={brand.voice_source_urls.length === 0 || regen.isPending}
            className="px-2.5 py-1 rounded-md bg-surface-container-high text-on-surface text-xs font-label font-medium disabled:opacity-40"
            title={brand.voice_source_urls.length === 0
              ? "Set voice_source_urls first (e.g. echoforge.biz pages)"
              : "Re-scrape sources and rebuild voice profile"}
          >
            {regen.isPending ? "Regenerating…" : "Regenerate voice"}
          </button>
        </div>
        {regenError && (
          <div className="text-[11px] font-label text-error">{regenError}</div>
        )}
      </div>
    </div>
  )
}


// ── Strategies tab ─────────────────────────────────────────────────────────────

function StrategiesTab({ brands, brandFilter }: { brands: ContentBrand[]; brandFilter: string | undefined }) {
  const queryClient = useQueryClient()
  const { data: strategies = [], isLoading } = useQuery({
    queryKey: ["ce", "strategies", brandFilter ?? "all"],
    queryFn: () => fetchContentStrategies(brandFilter),
  })

  const create = useMutation({
    mutationFn: (brandId: string) => createContentStrategy({ brand_id: brandId, period_days: 30 }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ce", "strategies"] }),
  })

  const approve = useMutation({
    mutationFn: approveContentStrategy,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ce", "strategies"] }),
  })

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-headline font-semibold text-base text-on-surface">Editorial Strategies</h2>
        <div className="flex gap-2">
          {brands.map((b) => (
            <button
              key={b.id}
              onClick={() => create.mutate(b.id)}
              disabled={create.isPending}
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
    </section>
  )
}

function StrategyCard({
  strategy, onApprove, approving,
}: { strategy: ContentStrategy; onApprove: () => void; approving: boolean }) {
  const [expanded, setExpanded] = useState(false)
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
            onClick={() => setExpanded(!expanded)}
            className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface text-sm font-label font-medium"
          >
            {expanded ? "Hide calendar" : "View calendar"}
          </button>
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
      {expanded && (
        <div className="mt-3 space-y-1 max-h-72 overflow-y-auto text-xs font-body">
          {strategy.calendar.map((slot, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 px-2 py-1 odd:bg-surface-container-low/40 rounded">
              <span className="col-span-2 text-on-surface-variant">{slot.date}</span>
              <span className="col-span-2 font-label">{slot.channel.split("_")[0]}</span>
              <span className="col-span-2 font-label">{slot.format}</span>
              <span className="col-span-6 text-on-surface">
                {slot.topic ?? slot.pillar ?? "—"}
              </span>
            </div>
          ))}
        </div>
      )}
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
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[10px] font-label font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${STATUS_COLOR[item.status] ?? ""}`}>
              {item.status}
            </span>
            <span className="text-xs font-label text-on-surface-variant">
              {item.format} · {item.channels.join(", ")}
            </span>
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
            <div className="text-xs font-body text-error bg-error-container/30 px-2 py-1 rounded">
              {item.error_message}
            </div>
          )}
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
          Each (brand × channel) pair needs an OAuth token before native publishing works. Without one,
          items fall back to assisted-send (deep link + manual confirm).
        </p>
      </div>

      {visibleBrands.length === 0 ? (
        <p className="text-sm text-on-surface-variant">Seed a brand first.</p>
      ) : (
        visibleBrands.map((b) => {
          const brandAccounts = accounts.filter((a) => a.brand_id === b.id)
          const connectedPlatforms = new Set(brandAccounts.filter((a) => a.has_token).map((a) => a.platform))

          return (
            <div key={b.id} className="bg-surface-container-lowest rounded-xl p-4 shadow-float space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-headline font-bold text-base text-on-surface">{b.name}</div>
                  <div className="text-xs font-label text-on-surface-variant">
                    {brandAccounts.filter((a) => a.has_token).length} connected ·{" "}
                    {brandAccounts.length - brandAccounts.filter((a) => a.has_token).length} assisted-only
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {OAUTH_PROVIDERS.map((p) => {
                    const allConnected = p.covers.every((c) => connectedPlatforms.has(c))
                    const key = `${b.id}:${p.id}`
                    return (
                      <button
                        key={p.id}
                        onClick={() => handleConnect(p.id, b.id)}
                        disabled={connecting === key}
                        className={[
                          "px-3 py-1.5 rounded-lg text-xs font-label font-medium",
                          allConnected
                            ? "bg-surface-container-high text-on-surface-variant"
                            : "bg-primary text-on-primary",
                          connecting === key ? "opacity-50" : "",
                        ].join(" ")}
                      >
                        {connecting === key ? "Redirecting…" : allConnected ? `Re-connect ${p.id}` : p.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              {brandAccounts.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-2 border-t border-outline-variant/15">
                  {brandAccounts.map((a) => (
                    <div key={a.id} className="bg-surface-container-low/40 rounded-lg p-2.5">
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="font-headline font-semibold text-xs text-on-surface">
                          {a.platform.replace(/_/g, " ")}
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
                        {a.account_name || a.account_id || "—"}
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
        })
      )}

      {isLoading && <p className="text-xs text-on-surface-variant">Refreshing…</p>}
    </section>
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
