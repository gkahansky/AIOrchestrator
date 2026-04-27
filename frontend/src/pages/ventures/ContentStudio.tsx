import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery, useMutation } from "@tanstack/react-query"
import { fetchPodcastOrders, createPodcastOrder } from "../../api"
import StatusBadge from "../../components/StatusBadge"
import PhaseBar from "../../components/PhaseBar"
import JobLinks from "../../components/JobLinks"

type Tab = "overview" | "new_order" | "orders"
type ServiceType = "show_notes" | "repurposing_pack"

const SERVICE_A_TIERS = [
  { id: "starter",  label: "Starter",  price: "$49",  description: "Show notes + timestamps + guest bio (≤60 min)" },
  { id: "standard", label: "Standard", price: "$79",  description: "Starter + full transcript + 5 social captions (≤60 min)" },
  { id: "premium",  label: "Premium",  price: "$119", description: "Standard + newsletter excerpt + SEO metadata (≤90 min)" },
] as const

const SERVICE_B_TIERS = [
  { id: "starter",  label: "Starter",  price: "£49",  description: "Transcript + show notes + 3 captions per platform (≤60 min)" },
  { id: "standard", label: "Standard", price: "£99",  description: "Starter + blog post + full newsletter draft + 5 captions (≤90 min)" },
  { id: "pro",      label: "Pro",      price: "£149", description: "Standard + brand voice injection + LinkedIn long-form + YouTube description (≤120 min)" },
] as const

const ALLOWED_AUDIO = ".mp3,.m4a,.wav,.webm,.mpeg,.mpga,.ogg,.flac"
const ALLOWED_ALL   = `${ALLOWED_AUDIO},.mp4,.mov,.mkv,.avi`

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function Overview() {
  return (
    <div className="space-y-6">
      {/* Service A */}
      <div>
        <h3 className="font-headline font-bold text-sm text-on-surface-variant uppercase tracking-wider mb-3">
          Service A — Podcast Show Notes
        </h3>
        <div className="grid grid-cols-3 gap-4">
          {SERVICE_A_TIERS.map((t) => (
            <div key={t.id} className="bg-surface-container-lowest rounded-xl p-5 shadow-float">
              <div className="font-headline font-bold text-2xl text-tertiary mb-1">{t.price}</div>
              <div className="font-label font-semibold text-base text-on-surface mb-1">{t.label}</div>
              <div className="text-sm font-body text-on-surface-variant">{t.description}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Service B */}
      <div>
        <h3 className="font-headline font-bold text-sm text-on-surface-variant uppercase tracking-wider mb-3">
          Service B — Content Repurposing Pack
        </h3>
        <div className="grid grid-cols-3 gap-4">
          {SERVICE_B_TIERS.map((t) => (
            <div key={t.id} className="bg-surface-container-lowest rounded-xl p-5 shadow-float border border-secondary/10">
              <div className="font-headline font-bold text-2xl text-secondary mb-1">{t.price}</div>
              <div className="font-label font-semibold text-base text-on-surface mb-1">{t.label}</div>
              <div className="text-sm font-body text-on-surface-variant">{t.description}</div>
            </div>
          ))}
        </div>
        <p className="text-xs font-label text-on-surface-variant mt-2">
          Accepts audio <em>or</em> video (MP4, MOV, MKV, AVI, WebM) up to 500 MB. Human-reviewed before delivery.
        </p>
      </div>

      {/* Pipeline */}
      <div className="bg-surface-container-lowest rounded-xl p-5 shadow-float">
        <h3 className="font-headline font-bold text-base text-on-surface mb-3">Pipeline Phases</h3>
        <div className="grid grid-cols-5 gap-2">
          {["Transcribe", "Generate", "Package", "Review", "Deliver"].map((phase, i) => (
            <div key={i} className="text-center">
              <div className="w-8 h-8 rounded-full bg-tertiary-fixed flex items-center justify-center mx-auto mb-1">
                <span className="text-xs font-label font-bold text-on-tertiary-fixed-variant">{i + 1}</span>
              </div>
              <p className="text-xs font-label text-on-surface-variant">{phase}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function NewOrderForm() {
  const navigate = useNavigate()
  const [serviceType, setServiceType] = useState<ServiceType>("show_notes")
  const [tier, setTier] = useState<string>("starter")
  const [clientEmail, setClientEmail] = useState("")
  const [showName, setShowName] = useState("")
  const [episodeTitle, setEpisodeTitle] = useState("")
  const [hostName, setHostName] = useState("")
  const [guestName, setGuestName] = useState("")
  const [niche, setNiche] = useState("")
  const [audience, setAudience] = useState("")
  const [showUrl, setShowUrl] = useState("")
  const [guestExpertise, setGuestExpertise] = useState("")
  const [specialInstructions, setSpecialInstructions] = useState("")
  const [mediaFile, setMediaFile] = useState<File | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const isServiceB = serviceType === "repurposing_pack"
  const tiers = isServiceB ? SERVICE_B_TIERS : SERVICE_A_TIERS
  const acceptAttr = isServiceB ? ALLOWED_ALL : ALLOWED_AUDIO

  // Reset tier when switching service to ensure valid tier for the service
  function handleServiceChange(svc: ServiceType) {
    setServiceType(svc)
    setTier("starter")
    setMediaFile(null)
    setErrors({})
  }

  const mutation = useMutation({
    mutationFn: createPodcastOrder,
    onSuccess: (data) => {
      navigate(`/jobs/${data.job_id}`)
    },
  })

  function validate() {
    const e: Record<string, string> = {}
    if (!mediaFile) {
      e.media = isServiceB ? "An audio or video file is required" : "An audio file is required"
    }
    if (!clientEmail.trim()) e.client_email = "Client email is required"
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(clientEmail)) e.client_email = "Must be a valid email"
    return e
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length > 0) { setErrors(errs); return }
    setErrors({})
    mutation.mutate({
      audio: mediaFile!,
      service_type: serviceType,
      tier: tier as "starter" | "standard" | "premium" | "pro",
      client_email: clientEmail,
      show_name: showName,
      episode_title: episodeTitle,
      host_name: hostName,
      guest_name: guestName,
      niche: niche,
      audience: audience,
      show_url: showUrl,
      guest_expertise: guestExpertise,
      special_instructions: specialInstructions,
    })
  }

  const isVideo = mediaFile
    ? [".mp4", ".mov", ".mkv", ".avi"].some((ext) => mediaFile.name.toLowerCase().endsWith(ext))
    : false

  return (
    <form onSubmit={handleSubmit} className="max-w-xl space-y-6">

      {/* Service Type selector */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-2 uppercase tracking-wider">
          Service <span className="text-error">*</span>
        </label>
        <div className="grid grid-cols-2 gap-2">
          {(
            [
              { id: "show_notes",      label: "Podcast Show Notes",      sub: "Audio → written content package", icon: "mic" },
              { id: "repurposing_pack", label: "Content Repurposing Pack", sub: "Audio or video → blog + captions + newsletter", icon: "movie" },
            ] as const
          ).map((s) => (
            <label
              key={s.id}
              className={`flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-colors ${
                serviceType === s.id
                  ? "bg-tertiary-fixed border border-tertiary/20"
                  : "bg-surface-container-low border border-transparent hover:bg-surface-container"
              }`}
            >
              <input
                type="radio"
                name="service_type"
                value={s.id}
                checked={serviceType === s.id}
                onChange={() => handleServiceChange(s.id)}
                className="accent-tertiary mt-0.5"
              />
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[16px] text-tertiary">{s.icon}</span>
                  <span className="text-sm font-label font-semibold text-on-surface">{s.label}</span>
                </div>
                <span className="text-xs text-on-surface-variant">{s.sub}</span>
              </div>
            </label>
          ))}
        </div>
        {isServiceB && (
          <p className="text-xs font-label text-secondary mt-2 flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">verified</span>
            Human-reviewed before delivery — every order, no exceptions.
          </p>
        )}
      </div>

      {/* Media file upload */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          {isServiceB ? "Audio or Video File" : "Audio File"} <span className="text-error">*</span>
        </label>
        <label
          className={`flex items-center gap-3 w-full px-4 py-3 rounded-xl border cursor-pointer transition-colors ${
            errors.media
              ? "border-error bg-error-container/10"
              : "border-transparent bg-surface-container-low hover:bg-surface-container"
          }`}
        >
          <span className="material-symbols-outlined text-[20px] text-on-surface-variant">
            {isVideo ? "movie" : "upload_file"}
          </span>
          <span className="text-sm font-label text-on-surface-variant flex-1 truncate">
            {mediaFile
              ? `${mediaFile.name} (${(mediaFile.size / 1024 / 1024).toFixed(1)} MB)`
              : isServiceB
              ? "Choose file — MP3, M4A, WAV, MP4, MOV, MKV, AVI, WebM…"
              : "Choose file — MP3, M4A, WAV, WebM, FLAC…"}
          </span>
          <input
            type="file"
            accept={acceptAttr}
            className="hidden"
            onChange={(e) => { setMediaFile(e.target.files?.[0] ?? null); setErrors((prev) => ({ ...prev, media: "" })) }}
          />
        </label>
        {isVideo && (
          <p className="text-xs font-label text-on-surface-variant mt-1 flex items-center gap-1">
            <span className="material-symbols-outlined text-[13px]">info</span>
            Audio will be extracted from the video before transcription.
          </p>
        )}
        {errors.media && <p className="text-xs text-error mt-1 font-label">{errors.media}</p>}
      </div>

      {/* Tier */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-2 uppercase tracking-wider">
          Tier <span className="text-error">*</span>
        </label>
        <div className="space-y-2">
          {tiers.map((t) => (
            <label
              key={t.id}
              className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-colors ${
                tier === t.id
                  ? "bg-tertiary-fixed border border-tertiary/20"
                  : "bg-surface-container-low border border-transparent hover:bg-surface-container"
              }`}
            >
              <input
                type="radio"
                name="tier"
                value={t.id}
                checked={tier === t.id}
                onChange={() => setTier(t.id)}
                className="accent-tertiary"
              />
              <div className="flex-1">
                <span className="text-sm font-label font-medium text-on-surface">{t.label}</span>
                <span className="text-xs text-on-surface-variant ml-2">{t.description}</span>
              </div>
              <span className="text-sm font-label font-bold text-tertiary">{t.price}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Customer Email */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          Customer Email <span className="text-error">*</span>
        </label>
        <input
          type="email"
          value={clientEmail}
          onChange={(e) => setClientEmail(e.target.value)}
          placeholder="client@example.com"
          className={`w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border ${
            errors.client_email ? "border-error" : "border-transparent"
          } focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors`}
        />
        {errors.client_email && <p className="text-xs text-error mt-1 font-label">{errors.client_email}</p>}
      </div>

      {/* Show / Channel Name */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          {isServiceB ? "Show / Channel Name" : "Show Name"}
        </label>
        <input
          type="text"
          value={showName}
          onChange={(e) => setShowName(e.target.value)}
          placeholder={isServiceB ? "My Podcast or YouTube Channel" : "My Podcast"}
          className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
        />
      </div>

      {/* Episode / Video Title */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          {isServiceB ? "Episode / Video Title" : "Episode Title"}
        </label>
        <input
          type="text"
          value={episodeTitle}
          onChange={(e) => setEpisodeTitle(e.target.value)}
          placeholder={isServiceB ? "Ep 42 — How to Build a Business" : "Episode 42 — How to Build a Business"}
          className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
        />
      </div>

      {/* Host Name */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          Host Name
        </label>
        <input
          type="text"
          value={hostName}
          onChange={(e) => setHostName(e.target.value)}
          placeholder="Jane Smith"
          className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
        />
      </div>

      {/* Guest Name */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          Guest Name
        </label>
        <input
          type="text"
          value={guestName}
          onChange={(e) => setGuestName(e.target.value)}
          placeholder="John Doe (leave blank if no guest)"
          className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
        />
      </div>

      {/* Niche + Audience (two columns) */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
            Content Niche
          </label>
          <input
            type="text"
            value={niche}
            onChange={(e) => setNiche(e.target.value)}
            placeholder="business, tech, health…"
            className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
            Target Audience
          </label>
          <input
            type="text"
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
            placeholder="early-stage SaaS founders…"
            className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
          />
        </div>
      </div>

      {/* Show Website URL + Guest Expertise (two columns) */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
            Show Website URL
          </label>
          <input
            type="url"
            value={showUrl}
            onChange={(e) => setShowUrl(e.target.value)}
            placeholder="https://yourshow.com"
            className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
          />
          <p className="text-xs text-on-surface-variant/60 mt-1 font-label">Required for Landing Page Audit add-on</p>
        </div>
        <div>
          <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
            Guest Expertise
          </label>
          <input
            type="text"
            value={guestExpertise}
            onChange={(e) => setGuestExpertise(e.target.value)}
            placeholder="SaaS growth, B2B sales, mindfulness…"
            className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
          />
          <p className="text-xs text-on-surface-variant/60 mt-1 font-label">Required for Guest Outreach add-on</p>
        </div>
      </div>

      {/* Special Instructions */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          Special Instructions
        </label>
        <textarea
          value={specialInstructions}
          onChange={(e) => setSpecialInstructions(e.target.value)}
          placeholder="Tone preferences, brand notes, sections to emphasise, topics to avoid…"
          rows={3}
          className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors resize-none"
        />
      </div>

      {mutation.error && (
        <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label">
          {(mutation.error as Error).message}
        </div>
      )}

      <button
        type="submit"
        disabled={mutation.isPending}
        className="w-full py-3 rounded-xl bg-gradient-to-br from-tertiary to-tertiary-container text-on-tertiary text-sm font-label font-semibold shadow-float hover:opacity-90 transition-opacity disabled:opacity-60"
      >
        {mutation.isPending ? "Creating Order…" : "Create Order"}
      </button>
    </form>
  )
}

function OrdersList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["podcastOrders"],
    queryFn: () => fetchPodcastOrders({ page_size: 50 }),
    refetchInterval: 30_000,
  })
  const navigate = useNavigate()

  if (error) {
    return (
      <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label">
        Failed to load orders: {(error as Error).message}
      </div>
    )
  }

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-container-low border-b border-outline-variant/10">
              {["Job ID", "Service", "File", "Show", "Tier", "Status", "Phase", "Created", "Actions"].map((h) => (
                <th
                  key={h}
                  className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/10">
            {isLoading
              ? Array(5).fill(null).map((_, i) => (
                  <tr key={i}>
                    {Array(9).fill(null).map((__, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 bg-surface-dim rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              : data?.items.map((job) => {
                  const svc = (job.input_data.service_type as string) || "show_notes"
                  const isB = svc === "repurposing_pack"
                  const inputType = (job.input_data.input_type as string) || "audio"
                  return (
                    <tr key={job.id} className="hover:bg-surface-container-low/40 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">
                        {job.id.slice(0, 8)}…
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-label font-semibold px-2 py-0.5 rounded-full ${
                          isB
                            ? "bg-secondary-container text-on-secondary-container"
                            : "bg-tertiary-container text-on-tertiary-container"
                        }`}>
                          {isB ? "Repurposing" : "Show Notes"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm font-label text-on-surface max-w-[140px] truncate">
                        <span className="flex items-center gap-1">
                          <span className="material-symbols-outlined text-[14px] text-on-surface-variant">
                            {inputType === "video" ? "movie" : "audio_file"}
                          </span>
                          {(job.input_data.audio_filename_suffix as string)
                            ? `file${job.input_data.audio_filename_suffix as string}`
                            : "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm font-label text-on-surface">
                        {(job.input_data.show_name as string) || "—"}
                      </td>
                      <td className="px-4 py-3 text-sm font-label text-on-surface capitalize">
                        {(job.input_data.tier as string) ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={job.status} />
                      </td>
                      <td className="px-4 py-3 min-w-[120px]">
                        <PhaseBar current={job.phase_current} total={job.phase_total} />
                      </td>
                      <td className="px-4 py-3 text-xs font-label text-on-surface-variant">
                        {formatDate(job.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-1.5">
                          <JobLinks outputData={job.output_data} />
                          <button
                            onClick={() => navigate(`/jobs/${job.id}`)}
                            className="text-xs font-label font-semibold text-primary hover:underline text-left"
                          >
                            View details
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
            {!isLoading && data?.items.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-sm font-label text-on-surface-variant">
                  No orders yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function ContentStudio() {
  const [tab, setTab] = useState<Tab>("overview")

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview",  label: "Overview" },
    { id: "new_order", label: "New Order" },
    { id: "orders",    label: "Orders" },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="material-symbols-outlined text-[24px] text-tertiary">mic</span>
            <h1 className="font-headline font-bold text-2xl text-on-surface">Content Studio</h1>
          </div>
          <p className="text-sm font-body text-on-surface-variant">
            EchoForge — Podcast Show Notes &amp; Content Repurposing Pack
          </p>
        </div>
        <button
          onClick={() => setTab("new_order")}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-br from-tertiary to-tertiary-container text-on-tertiary text-sm font-label font-semibold shadow-float hover:opacity-90 transition-opacity"
        >
          <span className="material-symbols-outlined text-[16px]">add</span>
          New Order
        </button>
      </div>

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

      {tab === "overview"  && <Overview />}
      {tab === "new_order" && <NewOrderForm />}
      {tab === "orders"    && <OrdersList />}
    </div>
  )
}
