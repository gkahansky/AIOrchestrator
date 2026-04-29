import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { createCRJob, fetchCRJobs, retryCRJob } from "../../api"
import StatusBadge from "../../components/StatusBadge"

type Tab = "cr_order" | "cr_orders"

const CR_PLANS = [
  { id: "free",    label: "Free",    price: "$0",   clips: 3,  description: "3 watermarked clips + captions" },
  { id: "starter", label: "Starter", price: "$29",  clips: 5,  description: "5 clips + show notes + transcript + captions" },
  { id: "pro",     label: "Pro",     price: "$79",  clips: 10, description: "10 clips + all text + Buffer scheduling (5 platforms)" },
  { id: "studio",  label: "Studio",  price: "$199", clips: 20, description: "20 clips + Creatomate templates + brand voice injection" },
] as const

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  })
}

function CROrderForm({ onSuccess }: { onSuccess: () => void }) {
  const queryClient = useQueryClient()
  const [plan, setPlan] = useState<string>("starter")
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [showName, setShowName] = useState("")
  const [episodeTitle, setEpisodeTitle] = useState("")
  const [hostName, setHostName] = useState("")
  const [guestName, setGuestName] = useState("")
  const [clientEmail, setClientEmail] = useState("")
  const [niche, setNiche] = useState("")
  const [audience, setAudience] = useState("")
  const [brandVoice, setBrandVoice] = useState("")
  const [clipInstructions, setClipInstructions] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: createCRJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crJobs"] })
      onSuccess()
    },
  })

  function validate() {
    const e: Record<string, string> = {}
    if (!videoFile) e.video = "A video file is required"
    if (!episodeTitle.trim()) e.episode_title = "Episode title is required"
    return e
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length > 0) { setErrors(errs); return }
    setErrors({})
    mutation.mutate({
      plan,
      video: videoFile!,
      show_name: showName,
      episode_title: episodeTitle,
      host_name: hostName,
      guest_name: guestName,
      client_email: clientEmail,
      niche: niche || "general",
      audience: audience || "general audience",
      brand_voice:       plan === "studio" ? brandVoice : "",
      clip_instructions: clipInstructions,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-xl space-y-6">
      {/* Plan */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-2 uppercase tracking-wider">
          Plan <span className="text-error">*</span>
        </label>
        <div className="space-y-2">
          {CR_PLANS.map((p) => (
            <label
              key={p.id}
              className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-colors ${
                plan === p.id
                  ? "bg-secondary-fixed border border-secondary/20"
                  : "bg-surface-container-low border border-transparent hover:bg-surface-container"
              }`}
            >
              <input
                type="radio"
                name="cr_plan"
                value={p.id}
                checked={plan === p.id}
                onChange={() => setPlan(p.id)}
                className="accent-secondary"
              />
              <div className="flex-1">
                <span className="text-sm font-label font-medium text-on-surface">{p.label}</span>
                <span className="text-xs text-on-surface-variant ml-2">{p.description}</span>
              </div>
              <span className="text-sm font-label font-bold text-secondary">{p.price}/mo</span>
            </label>
          ))}
        </div>
      </div>

      {/* Video file upload */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          Video File <span className="text-error">*</span>
        </label>
        <label
          className={`flex items-center gap-3 w-full px-4 py-3 rounded-xl border cursor-pointer transition-colors ${
            errors.video
              ? "border-error bg-error-container/10"
              : "border-transparent bg-surface-container-low hover:bg-surface-container"
          }`}
        >
          <span className="material-symbols-outlined text-[20px] text-on-surface-variant">movie</span>
          <span className="text-sm font-label text-on-surface-variant flex-1 truncate">
            {videoFile
              ? `${videoFile.name} (${(videoFile.size / 1024 / 1024).toFixed(1)} MB)`
              : "Choose video — MP4, MOV, MKV, AVI, WebM…"}
          </span>
          <input
            type="file"
            accept=".mp4,.mov,.mkv,.avi,.webm,.mpeg,.wmv"
            className="hidden"
            onChange={(e) => { setVideoFile(e.target.files?.[0] ?? null); setErrors((prev) => ({ ...prev, video: "" })) }}
          />
        </label>
        <p className="text-xs text-on-surface-variant/60 mt-1 font-label">
          Up to {Math.round(2000)} MB. Audio is extracted automatically before processing.
        </p>
        {errors.video && <p className="text-xs text-error mt-1 font-label">{errors.video}</p>}
      </div>

      {/* Episode Title */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          Episode / Video Title <span className="text-error">*</span>
        </label>
        <input
          type="text"
          value={episodeTitle}
          onChange={(e) => { setEpisodeTitle(e.target.value); setErrors((prev) => ({ ...prev, episode_title: "" })) }}
          placeholder="Ep 42 — How to Build a Business"
          className={`w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border ${
            errors.episode_title ? "border-error" : "border-transparent"
          } focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors`}
        />
        {errors.episode_title && <p className="text-xs text-error mt-1 font-label">{errors.episode_title}</p>}
      </div>

      {/* Show Name */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          Show / Channel Name
        </label>
        <input
          type="text"
          value={showName}
          onChange={(e) => setShowName(e.target.value)}
          placeholder="My Podcast or YouTube Channel"
          className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
        />
      </div>

      {/* Host + Guest */}
      <div className="grid grid-cols-2 gap-4">
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
        <div>
          <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
            Guest Name
          </label>
          <input
            type="text"
            value={guestName}
            onChange={(e) => setGuestName(e.target.value)}
            placeholder="John Doe (optional)"
            className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
          />
        </div>
      </div>

      {/* Niche + Audience */}
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

      {/* Client Email */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          Client Email
        </label>
        <input
          type="email"
          value={clientEmail}
          onChange={(e) => setClientEmail(e.target.value)}
          placeholder="client@example.com"
          className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
        />
      </div>

      {/* Brand Voice — Studio only */}
      {plan === "studio" && (
        <div>
          <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
            Brand Voice Guide
            <span className="ml-1 text-secondary normal-case font-normal">(Studio)</span>
          </label>
          <textarea
            value={brandVoice}
            onChange={(e) => setBrandVoice(e.target.value)}
            placeholder="Tone: conversational, authoritative. Avoid jargon. Always end with a CTA…"
            rows={3}
            className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors resize-none"
          />
        </div>
      )}

      {/* Clip instructions — optional hints for chapter selection */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          Clip Instructions
          <span className="ml-1 text-on-surface-variant/60 normal-case font-normal">(optional)</span>
        </label>
        <textarea
          value={clipInstructions}
          onChange={(e) => setClipInstructions(e.target.value)}
          placeholder="Focus on moments about X… avoid topics Y and Z… include the story at min 14…"
          rows={2}
          className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors resize-none"
        />
        <p className="text-xs text-on-surface-variant/60 mt-1 font-label">
          Hints for the AI — you can also select chapters interactively after transcription.
        </p>
      </div>

      {mutation.error && (
        <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label">
          {(mutation.error as Error).message}
        </div>
      )}

      <button
        type="submit"
        disabled={mutation.isPending}
        className="w-full py-3 rounded-xl bg-gradient-to-br from-secondary to-secondary-container text-on-secondary text-sm font-label font-semibold shadow-float hover:opacity-90 transition-opacity disabled:opacity-60"
      >
        {mutation.isPending ? "Queueing Job…" : "Queue Repurposing Job"}
      </button>
    </form>
  )
}

function CROrdersList() {
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ["crJobs"],
    queryFn: fetchCRJobs,
    refetchInterval: 15_000,
  })

  const retryMutation = useMutation({
    mutationFn: retryCRJob,
    onSuccess: () => {
      setExpanded(null)
      queryClient.invalidateQueries({ queryKey: ["crJobs"] })
    },
  })

  const planColor: Record<string, string> = {
    free:    "bg-surface-container text-on-surface-variant",
    starter: "bg-tertiary-container text-on-tertiary-container",
    pro:     "bg-secondary-container text-on-secondary-container",
    studio:  "bg-primary-container text-on-primary-container",
  }

  if (error) return (
    <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label">
      Failed to load jobs: {(error as Error).message}
    </div>
  )

  const jobs = data ?? []

  return (
    <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-container-low border-b border-outline-variant/10">
              {["Job ID", "Plan", "Episode", "Clips", "Status", "Created", "Actions"].map((h) => (
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
                    {Array(7).fill(null).map((__, j) => (
                      <td key={j} className="px-4 py-3"><div className="h-4 bg-surface-dim rounded animate-pulse" /></td>
                    ))}
                  </tr>
                ))
              : jobs.map((job) => (
                  <>
                    <tr key={job.id} className="hover:bg-surface-container-low/40 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">{job.id.slice(0, 8)}…</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-label font-semibold px-2 py-0.5 rounded-full capitalize ${planColor[job.plan] ?? planColor.free}`}>
                          {job.plan}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm font-label text-on-surface max-w-[200px] truncate">
                        {job.episode_title || job.show_name || "—"}
                      </td>
                      <td className="px-4 py-3 text-sm font-label text-on-surface">
                        {job.clip_count != null ? `${job.clip_count} clips` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={job.status} />
                      </td>
                      <td className="px-4 py-3 text-xs font-label text-on-surface-variant whitespace-nowrap">
                        {formatDate(job.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setExpanded(expanded === job.id ? null : job.id)}
                            className="text-xs font-label font-semibold text-primary hover:underline"
                          >
                            {expanded === job.id ? "Hide" : "Details"}
                          </button>
                          {job.status === "failed" && (
                            <button
                              onClick={() => retryMutation.mutate(job.id)}
                              disabled={retryMutation.isPending}
                              className="text-xs font-label font-semibold text-secondary hover:underline disabled:opacity-50"
                            >
                              Retry
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expanded === job.id && (
                      <tr key={`${job.id}-detail`} className="bg-surface-container-low/30">
                        <td colSpan={7} className="px-6 py-4">
                          <div className="space-y-2 text-xs font-label">
                            <div className="flex gap-2">
                              <span className="text-on-surface-variant w-24 shrink-0">Job ID</span>
                              <span className="font-mono text-on-surface">{job.id}</span>
                            </div>
                            <div className="flex gap-2">
                              <span className="text-on-surface-variant w-24 shrink-0">Status</span>
                              <StatusBadge status={job.status} />
                            </div>
                            <div className="flex gap-2">
                              <span className="text-on-surface-variant w-24 shrink-0">Plan</span>
                              <span className="text-on-surface capitalize">{job.plan}</span>
                            </div>
                            <div className="flex gap-2">
                              <span className="text-on-surface-variant w-24 shrink-0">Episode</span>
                              <span className="text-on-surface">{job.episode_title || "—"}</span>
                            </div>
                            <div className="flex gap-2">
                              <span className="text-on-surface-variant w-24 shrink-0">Show</span>
                              <span className="text-on-surface">{job.show_name || "—"}</span>
                            </div>
                            {job.error_message && (
                              <div className="flex gap-2">
                                <span className="text-error w-24 shrink-0">Error</span>
                                <span className="text-error break-all">{job.error_message}</span>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
            {!isLoading && jobs.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-sm font-label text-on-surface-variant">
                  No jobs yet — submit a video above to get started.
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
  const [tab, setTab] = useState<Tab>("cr_order")

  const tabs: { id: Tab; label: string }[] = [
    { id: "cr_order",  label: "New Order" },
    { id: "cr_orders", label: "Jobs" },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="material-symbols-outlined text-[24px] text-secondary">movie</span>
            <h1 className="font-headline font-bold text-2xl text-on-surface">Content Studio</h1>
          </div>
          <p className="text-sm font-body text-on-surface-variant">
            EchoForge — Video Content Repurposing
          </p>
        </div>
        <button
          onClick={() => setTab("cr_order")}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-br from-secondary to-secondary-container text-on-secondary text-sm font-label font-semibold shadow-float hover:opacity-90 transition-opacity"
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

      {tab === "cr_order"  && <CROrderForm onSuccess={() => setTab("cr_orders")} />}
      {tab === "cr_orders" && <CROrdersList />}
    </div>
  )
}
