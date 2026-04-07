import { useState } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { useJob, useApproveJob, useRejectJob, useRetryJob } from "../hooks/useJobs"
import StatusBadge from "../components/StatusBadge"
import type { JobStatus } from "../types"

interface PhaseStep {
  name: string
  state: "complete" | "active" | "pending" | "failed"
  timestamp?: string
}

interface ResourceLink {
  label: string
  url: string
}

// Statuses where the current phase has actually finished (no spinner)
const DONE_STATUSES = new Set([
  "completed", "delivered", "published", "approved",
  "review_pending", "rejected", "cancelled",
])

function buildPhaseSteps(
  status: JobStatus,
  phaseCurrent: number | null,
  phaseTotal: number | null
): PhaseStep[] {
  const total = phaseTotal ?? 0
  const current = phaseCurrent ?? 0

  return Array.from({ length: total }, (_, i) => {
    const phaseNum = i + 1
    if (phaseNum < current) return { name: `Phase ${phaseNum}`, state: "complete" as const }
    if (phaseNum === current) {
      if (status === "failed") return { name: `Phase ${phaseNum}`, state: "failed" as const }
      if (DONE_STATUSES.has(status)) return { name: `Phase ${phaseNum}`, state: "complete" as const }
      return { name: `Phase ${phaseNum}`, state: "active" as const }
    }
    return { name: `Phase ${phaseNum}`, state: "pending" as const }
  })
}

function StepIcon({ state }: { state: PhaseStep["state"] }) {
  if (state === "complete")
    return (
      <span className="material-symbols-outlined text-[20px] text-emerald-600">check_circle</span>
    )
  if (state === "active")
    return (
      <span className="material-symbols-outlined text-[20px] text-primary animate-spin">
        progress_activity
      </span>
    )
  if (state === "failed")
    return (
      <span className="material-symbols-outlined text-[20px] text-error">cancel</span>
    )
  return (
    <span className="material-symbols-outlined text-[20px] text-on-surface-variant/40">
      radio_button_unchecked
    </span>
  )
}

function formatDate(iso: string | null) {
  if (!iso) return "—"
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {}
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function buildResourceLinks(outputData: Record<string, unknown>): ResourceLink[] {
  const candidates: ResourceLink[] = [
    { label: "Open Report", url: asString(outputData.drive_report_link) },
    { label: "Open Drive Folder", url: asString(outputData.drive_folder_link) },
    { label: "Open Google Doc", url: asString(outputData.gdoc_url) },
    { label: "Open Sample PDF", url: asString(outputData.drive_sample_pdf_link) || asString(outputData.drive_sample_PDF_link) },
  ]

  const seen = new Set<string>()
  return candidates.filter((item) => {
    if (!item.url || !/^https?:\/\//.test(item.url) || seen.has(item.url)) return false
    seen.add(item.url)
    return true
  })
}

export default function JobDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: job, isLoading, error } = useJob(id ?? "")
  const approve = useApproveJob()
  const reject = useRejectJob()
  const retry = useRetryJob()

  const [notes, setNotes] = useState("")
  const [actionDone, setActionDone] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState(false)

  async function handleApprove() {
    if (!id) return
    await approve.mutateAsync({ id, notes })
    setActionDone("approved")
  }

  async function handleReject() {
    if (!id) return
    await reject.mutateAsync({ id, notes })
    setActionDone("rejected")
  }

  async function handleRetry() {
    if (!id) return
    await retry.mutateAsync({ id })
    setActionDone("retried")
  }

  async function handleCancel() {
    if (!id) return
    setCancelling(true)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || "https://api.planbadmin.com"}/api/jobs/${id}/cancel`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("api_token")}` },
      })
      if (!res.ok) throw new Error("Cancel failed")
      setActionDone("cancelled")
      setTimeout(() => navigate(-1), 1500)
    } catch (e) {
      alert((e as Error).message)
    } finally {
      setCancelling(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 bg-surface-dim rounded animate-pulse" />
        <div className="grid grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 bg-surface-container-lowest rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="bg-error-container text-on-error-container rounded-xl px-5 py-4 text-sm font-label">
        <p className="font-semibold mb-1">Failed to load job</p>
        <p>{(error as Error)?.message ?? "Job not found"}</p>
        <Link to="/" className="text-primary font-semibold mt-3 inline-block hover:underline">
          ← Back to Dashboard
        </Link>
      </div>
    )
  }

  const steps = buildPhaseSteps(job.status, job.phase_current, job.phase_total)
  const isReviewPending = job.status === "review_pending"
  const isFailed = job.status === "failed"
  const outputData = asRecord(job.output_data)
  const resourceLinks = buildResourceLinks(outputData)

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm font-label text-on-surface-variant">
        <Link to="/" className="hover:text-primary transition-colors">
          Dashboard
        </Link>
        <span className="material-symbols-outlined text-[14px]">chevron_right</span>
        <span className="text-on-surface">Job {job.id.slice(0, 8)}…</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="font-headline font-bold text-2xl text-on-surface">
              {job.venture.replace(/_/g, " ")}
            </h1>
            <StatusBadge status={job.status} />
          </div>
          <p className="text-sm font-label text-on-surface-variant font-mono">{job.id}</p>
        </div>
        <div className="flex items-center gap-3">
          {isReviewPending && !actionDone && (
            <button
              onClick={handleApprove}
              disabled={approve.isPending}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 text-white text-xs font-label font-semibold hover:bg-emerald-700 transition-colors disabled:opacity-60"
            >
              <span className="material-symbols-outlined text-[14px]">check_circle</span>
              {approve.isPending ? "Approving…" : "Approve"}
            </button>
          )}
          {!["delivered", "published", "completed", "approved", "failed", "cancelled", "rejected"].includes(job.status) && !actionDone && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-error/30 text-error text-xs font-label font-semibold hover:bg-error-container transition-colors disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[14px]">cancel</span>
              {cancelling ? "Cancelling…" : "Cancel Job"}
            </button>
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
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
          <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">
            Created
          </p>
          <p className="text-sm font-label text-on-surface">{formatDate(job.created_at)}</p>
        </div>
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
          <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">
            Started
          </p>
          <p className="text-sm font-label text-on-surface">{formatDate(job.started_at)}</p>
        </div>
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
          <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">
            Completed
          </p>
          <p className="text-sm font-label text-on-surface">{formatDate(job.completed_at)}</p>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Phase Timeline */}
        <div className="col-span-5 bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
          <div className="px-5 py-4 border-b border-outline-variant/15">
            <h2 className="font-headline font-bold text-sm text-on-surface">Pipeline Timeline</h2>
          </div>
          <div className="px-5 py-4 space-y-0">
            {steps.length === 0 ? (
              <p className="text-sm font-label text-on-surface-variant py-4">
                No phase data available
              </p>
            ) : (
              steps.map((step, i) => (
                <div key={i} className="flex gap-3 pb-0">
                  <div className="flex flex-col items-center">
                    <StepIcon state={step.state} />
                    {i < steps.length - 1 && (
                      <div
                        className={`w-px flex-1 my-1 min-h-[24px] ${
                          step.state === "complete"
                            ? "bg-emerald-300"
                            : "bg-outline-variant/30"
                        }`}
                      />
                    )}
                  </div>
                  <div className="pb-4">
                    <p
                      className={`text-sm font-label font-medium ${
                        step.state === "active"
                          ? "text-primary"
                          : step.state === "complete"
                          ? "text-on-surface"
                          : step.state === "failed"
                          ? "text-error"
                          : "text-on-surface-variant/50"
                      }`}
                    >
                      {step.name}
                    </p>
                    {step.timestamp && (
                      <p className="text-xs font-label text-on-surface-variant">{step.timestamp}</p>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Input / Output data */}
        <div className="col-span-7 space-y-4">
          {resourceLinks.length > 0 && (
            <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
              <div className="px-5 py-4 border-b border-outline-variant/15">
                <h2 className="font-headline font-bold text-sm text-on-surface">Deliverables</h2>
              </div>
              <div className="px-5 py-4 flex flex-wrap gap-3">
                {resourceLinks.map((link) => (
                  <a
                    key={`${link.label}-${link.url}`}
                    href={link.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary/10 text-primary text-sm font-label font-semibold hover:bg-primary/15 transition-colors"
                  >
                    <span className="material-symbols-outlined text-[16px]">open_in_new</span>
                    {link.label}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Input Data */}
          <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
            <div className="px-5 py-4 border-b border-outline-variant/15">
              <h2 className="font-headline font-bold text-sm text-on-surface">Input Data</h2>
            </div>
            <div className="px-5 py-4">
              <pre className="text-xs font-mono text-on-surface-variant bg-surface-container-low rounded-lg p-3 overflow-x-auto overflow-y-auto whitespace-pre-wrap max-h-40">
                {JSON.stringify(job.input_data, null, 2)}
              </pre>
            </div>
          </div>

          {/* Output Data */}
          {Object.keys(job.output_data).length > 0 && (
            <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
              <div className="px-5 py-4 border-b border-outline-variant/15">
                <h2 className="font-headline font-bold text-sm text-on-surface">Output Data</h2>
              </div>
              <div className="px-5 py-4">
                <pre className="text-xs font-mono text-on-surface-variant bg-surface-container-low rounded-lg p-3 overflow-x-auto overflow-y-auto whitespace-pre-wrap max-h-72">
                  {JSON.stringify(outputData, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {/* Error */}
          {job.error_message && (
            <div className="bg-error-container rounded-xl px-4 py-3">
              <p className="text-xs font-label font-semibold uppercase tracking-wider text-error mb-1">
                Error
              </p>
              <p className="text-sm font-label text-on-error-container">{job.error_message}</p>
            </div>
          )}
        </div>
      </div>

      {/* Action bar */}
      {(isReviewPending || isFailed) && !actionDone && (
        <div className="bg-surface-container-lowest rounded-xl shadow-float px-6 py-5 space-y-4">
          <h2 className="font-headline font-bold text-sm text-on-surface">Actions</h2>

          {isReviewPending && (
            <>
              {resourceLinks.length > 0 && (
                <div className="flex flex-wrap gap-3">
                  {resourceLinks.map((link) => (
                    <a
                      key={`review-${link.label}-${link.url}`}
                      href={link.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-primary/20 text-primary text-sm font-label font-semibold hover:bg-primary/5 transition-colors"
                    >
                      <span className="material-symbols-outlined text-[16px]">description</span>
                      {link.label}
                    </a>
                  ))}
                </div>
              )}
              <div>
                <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
                  Notes (optional)
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  placeholder="Add review notes…"
                  className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 resize-none transition-colors"
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleReject}
                  disabled={reject.isPending}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-error-container text-error text-sm font-label font-semibold hover:bg-error/10 transition-colors disabled:opacity-60"
                >
                  <span className="material-symbols-outlined text-[16px]">cancel</span>
                  {reject.isPending ? "Rejecting…" : "Reject"}
                </button>
              </div>
            </>
          )}

          {isFailed && (
            <button
              onClick={handleRetry}
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
          <p className="text-sm font-label font-medium text-emerald-800 capitalize">
            Job {actionDone} successfully.
          </p>
        </div>
      )}

      {/* Mutation errors */}
      {(approve.error || reject.error || retry.error) && (
        <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label">
          {((approve.error || reject.error || retry.error) as Error).message}
        </div>
      )}
    </div>
  )
}
