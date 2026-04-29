import { useState, useEffect } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { fetchCRJob, approveCRJob, retryCRJob, approveCRJobChapters } from "../api"
import StatusBadge from "../components/StatusBadge"

// Named CR pipeline phases (includes chapter_review gate after transcription)
const CR_PHASES = [
  { label: "Download video",      activeStatus: "downloading"     },
  { label: "Transcribe audio",    activeStatus: "transcribing"    },
  { label: "Chapter review",      activeStatus: "chapter_review"  },
  { label: "Score clip virality", activeStatus: "scoring"         },
  { label: "Process clips",       activeStatus: "processing"      },
  { label: "Generate text",       activeStatus: "generating_text" },
  { label: "Package & upload",    activeStatus: "packaging"       },
  { label: "Human review",        activeStatus: "review_pending"  },
]

const PHASE_ORDER = [
  "pending", "downloading", "transcribing", "chapter_review", "scoring",
  "processing", "generating_text", "packaging", "review_pending", "delivered",
]

type PhaseState = "complete" | "active" | "pending" | "failed"

function getPhaseState(phaseActiveStatus: string, jobStatus: string): PhaseState {
  if (jobStatus === "delivered") return "complete"
  if (jobStatus === "failed")    return "pending"

  const phaseIdx   = PHASE_ORDER.indexOf(phaseActiveStatus)
  const currentIdx = PHASE_ORDER.indexOf(jobStatus)
  if (phaseIdx < currentIdx)  return "complete"
  if (phaseIdx === currentIdx) return "active"
  return "pending"
}

function StepIcon({ state }: { state: PhaseState }) {
  if (state === "complete")
    return <span className="material-symbols-outlined text-[20px] text-emerald-600">check_circle</span>
  if (state === "active")
    return <span className="material-symbols-outlined text-[20px] text-primary animate-spin">progress_activity</span>
  if (state === "failed")
    return <span className="material-symbols-outlined text-[20px] text-error">cancel</span>
  return <span className="material-symbols-outlined text-[20px] text-on-surface-variant/40">radio_button_unchecked</span>
}

function formatDate(iso: string | null | undefined) {
  if (!iso) return "—"
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
  })
}

function formatDuration(s: number | null | undefined) {
  if (!s) return "—"
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}m ${sec}s`
}

function driveFileUrl(id: string | null | undefined, type: "file" | "folder") {
  if (!id) return null
  return type === "folder"
    ? `https://drive.google.com/drive/folders/${id}`
    : `https://drive.google.com/file/d/${id}/view`
}

const planColor: Record<string, string> = {
  free:    "bg-surface-container text-on-surface-variant",
  starter: "bg-tertiary-container text-on-tertiary-container",
  pro:     "bg-secondary-container text-on-secondary-container",
  studio:  "bg-primary-container text-on-primary-container",
}

export default function CRJobDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [actionDone, setActionDone] = useState<string | null>(null)
  const [selectedChapterIds, setSelectedChapterIds] = useState<Set<number>>(new Set())

  const { data: job, isLoading, error } = useQuery({
    queryKey: ["crJob", id],
    queryFn: () => fetchCRJob(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s && ["chapter_review", "review_pending", "delivered", "failed"].includes(s)
        ? false
        : 10_000
    },
  })

  const approve = useMutation({
    mutationFn: () => approveCRJob(id!),
    onSuccess: () => {
      setActionDone("approved")
      queryClient.invalidateQueries({ queryKey: ["crJob", id] })
      queryClient.invalidateQueries({ queryKey: ["crJobs"] })
    },
  })

  const retry = useMutation({
    mutationFn: () => retryCRJob(id!),
    onSuccess: () => {
      setActionDone("retried")
      queryClient.invalidateQueries({ queryKey: ["crJob", id] })
      queryClient.invalidateQueries({ queryKey: ["crJobs"] })
    },
  })

  // Pre-check chapters suggested by clip_instructions when job first reaches chapter_review
  useEffect(() => {
    if (job?.status === "chapter_review" && job.suggested_chapter_ids?.length) {
      setSelectedChapterIds(new Set(job.suggested_chapter_ids))
    }
  }, [job?.status, job?.suggested_chapter_ids])

  const approveChapters = useMutation({
    mutationFn: (ids: number[] | null) => approveCRJobChapters(id!, ids),
    onSuccess: () => {
      setActionDone("chapters approved")
      queryClient.invalidateQueries({ queryKey: ["crJob", id] })
      queryClient.invalidateQueries({ queryKey: ["crJobs"] })
    },
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 bg-surface-dim rounded animate-pulse" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="h-24 bg-surface-container-lowest rounded-xl animate-pulse" />)}
        </div>
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="bg-error-container text-on-error-container rounded-xl px-5 py-4 text-sm font-label">
        <p className="font-semibold mb-1">Failed to load job</p>
        <p>{(error as Error)?.message ?? "Job not found"}</p>
        <Link to="/" className="text-primary font-semibold mt-3 inline-block hover:underline">← Back to Dashboard</Link>
      </div>
    )
  }

  const isReviewPending  = job.status === "review_pending"
  const isChapterReview  = job.status === "chapter_review"
  const isFailed         = job.status === "failed"
  const folderUrl        = driveFileUrl(job.drive_folder_id, "folder")
  const chapters         = job.chapters ?? []

  function toggleChapter(idx: number) {
    setSelectedChapterIds(prev => {
      const next = new Set(prev)
      next.has(idx) ? next.delete(idx) : next.add(idx)
      return next
    })
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm font-label text-on-surface-variant">
        <Link to="/" className="hover:text-primary transition-colors">Dashboard</Link>
        <span className="material-symbols-outlined text-[14px]">chevron_right</span>
        <Link to="/ventures/content-studio" className="hover:text-primary transition-colors">Content Studio</Link>
        <span className="material-symbols-outlined text-[14px]">chevron_right</span>
        <span className="text-on-surface">CR Job {job.id.slice(0, 8)}…</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="font-headline font-bold text-2xl text-on-surface">Content Repurposing</h1>
            <StatusBadge status={job.status} />
            <span className={`text-xs font-label font-semibold px-2 py-0.5 rounded-full capitalize ${planColor[job.plan] ?? planColor.free}`}>
              {job.plan}
            </span>
          </div>
          <p className="text-sm font-label text-on-surface-variant">
            {job.episode_title || job.show_name || "Untitled episode"}
          </p>
          <p className="text-xs font-mono text-on-surface-variant/60 mt-0.5">{job.id}</p>
        </div>
        <div className="flex items-center gap-3">
          {isReviewPending && !actionDone && (
            <button
              onClick={() => approve.mutate()}
              disabled={approve.isPending}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 text-white text-xs font-label font-semibold hover:bg-emerald-700 transition-colors disabled:opacity-60"
            >
              <span className="material-symbols-outlined text-[14px]">check_circle</span>
              {approve.isPending ? "Approving…" : "Approve & Deliver"}
            </button>
          )}
          {folderUrl && (
            <a
              href={folderUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-outline-variant/30 text-xs font-label font-medium text-on-surface-variant hover:bg-surface-container-low transition-colors"
            >
              <span className="material-symbols-outlined text-[14px]">folder_open</span>
              Open Drive Folder
            </a>
          )}
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1 text-sm font-label text-on-surface-variant hover:text-primary transition-colors"
          >
            <span className="material-symbols-outlined text-[18px]">arrow_back</span>
            Back
          </button>
        </div>
      </div>

      {/* Meta cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
          <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">Created</p>
          <p className="text-sm font-label text-on-surface">{formatDate(job.created_at)}</p>
        </div>
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
          <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">Completed</p>
          <p className="text-sm font-label text-on-surface">{formatDate(job.completed_at)}</p>
        </div>
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
          <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">Duration</p>
          <p className="text-sm font-label text-on-surface">{formatDuration(job.video_duration_s)}</p>
        </div>
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
          <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">Clips</p>
          <p className="text-sm font-label text-on-surface">
            {job.clip_count != null ? `${job.clip_count} clips` : job.clips.length > 0 ? `${job.clips.length} clips` : "—"}
          </p>
        </div>
      </div>

      {/* Error banner */}
      {job.error_message && (
        <div className="bg-error-container rounded-xl px-4 py-3">
          <p className="text-xs font-label font-semibold uppercase tracking-wider text-error mb-1">Error</p>
          <p className="text-sm font-label text-on-error-container break-all">{job.error_message}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Phase Timeline */}
        <div className="md:col-span-4 bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
          <div className="px-5 py-4 border-b border-outline-variant/15">
            <h2 className="font-headline font-bold text-sm text-on-surface">Pipeline Phases</h2>
          </div>
          <div className="px-5 py-4 space-y-0">
            {CR_PHASES.map((phase, i) => {
              const state = getPhaseState(phase.activeStatus, job.status)
              return (
                <div key={phase.activeStatus} className="flex gap-3 pb-0">
                  <div className="flex flex-col items-center">
                    <StepIcon state={state} />
                    {i < CR_PHASES.length - 1 && (
                      <div className={`w-px flex-1 my-1 min-h-[24px] ${state === "complete" ? "bg-emerald-300" : "bg-outline-variant/30"}`} />
                    )}
                  </div>
                  <div className="pb-4">
                    <p className={`text-sm font-label font-medium ${
                      state === "active"   ? "text-primary" :
                      state === "complete" ? "text-on-surface" :
                      state === "failed"   ? "text-error" :
                      "text-on-surface-variant/50"
                    }`}>
                      {phase.label}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right column */}
        <div className="md:col-span-8 space-y-4">
          {/* Chapter review panel — shown when status=chapter_review */}
          {isChapterReview && chapters.length > 0 && !actionDone && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl shadow-float overflow-hidden">
              <div className="px-5 py-4 border-b border-amber-200 flex items-center gap-2 flex-wrap">
                <span className="material-symbols-outlined text-[18px] text-amber-600">rate_review</span>
                <h2 className="font-headline font-bold text-sm text-amber-900">Select Chapters to Clip</h2>
                {job.suggested_chapter_ids?.length ? (
                  <span className="text-[11px] font-label px-2 py-0.5 bg-amber-200 text-amber-800 rounded-full">
                    AI pre-selected {job.suggested_chapter_ids.length} from your instructions
                  </span>
                ) : null}
                <span className="ml-auto text-xs font-label text-amber-700">
                  {selectedChapterIds.size > 0
                    ? `${selectedChapterIds.size} of ${chapters.length} selected`
                    : "None selected — will use full episode"}
                </span>
              </div>
              <div className="divide-y divide-amber-100">
                {chapters.map(ch => {
                  const isSelected = selectedChapterIds.has(ch.index)
                  const startMin = Math.floor(ch.start_s / 60)
                  const startSec = Math.floor(ch.start_s % 60)
                  const endMin   = Math.floor(ch.end_s / 60)
                  const endSec   = Math.floor(ch.end_s % 60)
                  return (
                    <label
                      key={ch.index}
                      className={`flex gap-3 px-5 py-3 cursor-pointer transition-colors ${isSelected ? "bg-amber-100" : "hover:bg-amber-50/60"}`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleChapter(ch.index)}
                        className="mt-1 accent-amber-600 shrink-0"
                      />
                      <div className="min-w-0">
                        <p className="text-sm font-label font-semibold text-amber-900">{ch.title}</p>
                        <p className="text-xs font-label text-amber-700 mt-0.5">{ch.summary}</p>
                        <p className="text-[11px] font-mono text-amber-600 mt-1">
                          {startMin}:{String(startSec).padStart(2,"0")} – {endMin}:{String(endSec).padStart(2,"0")}
                        </p>
                      </div>
                    </label>
                  )
                })}
              </div>
              <div className="px-5 py-4 bg-amber-50 border-t border-amber-200 flex flex-wrap gap-3">
                <button
                  onClick={() => approveChapters.mutate(selectedChapterIds.size > 0 ? Array.from(selectedChapterIds) : null)}
                  disabled={approveChapters.isPending}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-600 text-white text-sm font-label font-semibold hover:bg-amber-700 transition-colors disabled:opacity-60"
                >
                  <span className="material-symbols-outlined text-[15px]">play_arrow</span>
                  {approveChapters.isPending
                    ? "Processing…"
                    : selectedChapterIds.size > 0
                      ? `Clip from ${selectedChapterIds.size} chapter${selectedChapterIds.size > 1 ? "s" : ""}`
                      : "Clip from full episode"}
                </button>
                {selectedChapterIds.size > 0 && (
                  <button
                    onClick={() => setSelectedChapterIds(new Set())}
                    className="text-xs font-label text-amber-700 hover:text-amber-900 transition-colors"
                  >
                    Clear selection
                  </button>
                )}
              </div>
              {approveChapters.error && (
                <div className="px-5 py-3 bg-error-container text-on-error-container text-xs font-label">
                  {(approveChapters.error as Error).message}
                </div>
              )}
            </div>
          )}

          {/* Clips table */}
          {job.clips.length > 0 && (
            <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
              <div className="px-5 py-4 border-b border-outline-variant/15">
                <h2 className="font-headline font-bold text-sm text-on-surface">
                  Clips — {job.clips.length}
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-container-low border-b border-outline-variant/10">
                      {["#", "Window", "Score", "Hook", "Files"].map(h => (
                        <th key={h} className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/10">
                    {job.clips.map(clip => {
                      const dur = Math.round(clip.end_s - clip.start_s)
                      const score = clip.virality_score != null ? (clip.virality_score * 100).toFixed(0) : "—"
                      const clipUrl  = driveFileUrl(clip.drive_clip_id, "file")
                      const thumbUrl = driveFileUrl(clip.drive_thumbnail_id, "file")
                      return (
                        <tr key={clip.id} className="hover:bg-surface-container-low/40 transition-colors">
                          <td className="px-4 py-3 text-xs font-label text-on-surface-variant">{clip.clip_index + 1}</td>
                          <td className="px-4 py-3 text-xs font-label text-on-surface-variant whitespace-nowrap">
                            {Math.floor(clip.start_s / 60)}:{String(Math.floor(clip.start_s % 60)).padStart(2, "0")} – {Math.floor(clip.end_s / 60)}:{String(Math.floor(clip.end_s % 60)).padStart(2, "0")}
                            <span className="ml-1 text-on-surface-variant/60">({dur}s)</span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`text-xs font-label font-bold ${Number(score) >= 70 ? "text-emerald-600" : Number(score) >= 50 ? "text-amber-600" : "text-on-surface-variant"}`}>
                              {score}%
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs font-label text-on-surface max-w-[200px] truncate">
                            {clip.hook || clip.title || "—"}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              {clipUrl && (
                                <a href={clipUrl} target="_blank" rel="noopener noreferrer"
                                  className="text-xs font-label font-semibold text-primary hover:underline flex items-center gap-0.5">
                                  <span className="material-symbols-outlined text-[13px]">movie</span> Clip
                                </a>
                              )}
                              {thumbUrl && (
                                <a href={thumbUrl} target="_blank" rel="noopener noreferrer"
                                  className="text-xs font-label font-semibold text-secondary hover:underline flex items-center gap-0.5">
                                  <span className="material-symbols-outlined text-[13px]">image</span> Thumb
                                </a>
                              )}
                              {!clipUrl && !thumbUrl && <span className="text-xs text-on-surface-variant/60">Processing…</span>}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Input data */}
          <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
            <div className="px-5 py-4 border-b border-outline-variant/15">
              <h2 className="font-headline font-bold text-sm text-on-surface">Order Details</h2>
            </div>
            <div className="px-5 py-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm font-label">
              {[
                ["Show", job.show_name],
                ["Episode", job.episode_title],
                ["Client", job.client_email],
                ["Plan", job.plan],
              ].map(([label, value]) => value ? (
                <div key={label} className="flex flex-col">
                  <span className="text-[11px] uppercase tracking-wider text-on-surface-variant">{label}</span>
                  <span className="text-on-surface capitalize">{value}</span>
                </div>
              ) : null)}
            </div>
          </div>
        </div>
      </div>

      {/* Action bar */}
      {(isReviewPending || isFailed) && !actionDone && (
        <div className="bg-surface-container-lowest rounded-xl shadow-float px-6 py-5 space-y-4">
          <h2 className="font-headline font-bold text-sm text-on-surface">Actions</h2>
          {isReviewPending && (
            <div className="flex gap-3">
              <button
                onClick={() => approve.mutate()}
                disabled={approve.isPending}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 text-white text-sm font-label font-semibold hover:bg-emerald-700 transition-colors disabled:opacity-60"
              >
                <span className="material-symbols-outlined text-[16px]">check_circle</span>
                {approve.isPending ? "Approving…" : "Approve & Deliver to Client"}
              </button>
            </div>
          )}
          {isFailed && (
            <button
              onClick={() => retry.mutate()}
              disabled={retry.isPending}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-label font-semibold hover:opacity-90 transition-opacity disabled:opacity-60"
            >
              <span className="material-symbols-outlined text-[16px]">replay</span>
              {retry.isPending ? "Retrying…" : "Retry Job"}
            </button>
          )}
        </div>
      )}

      {/* Post-action confirmation */}
      {actionDone && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-5 py-4 flex items-center gap-3">
          <span className="material-symbols-outlined text-[20px] text-emerald-600">check_circle</span>
          <p className="text-sm font-label font-medium text-emerald-800 capitalize">Job {actionDone} successfully.</p>
        </div>
      )}

      {/* Mutation errors */}
      {(approve.error || retry.error) && (
        <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label">
          {((approve.error || retry.error) as Error).message}
        </div>
      )}
    </div>
  )
}
