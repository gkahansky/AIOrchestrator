import { useState } from "react"
import { Link } from "react-router-dom"
import { useDashboard } from "../hooks/useDashboard"
import { useJobs, useRetryJob, useCancelJob } from "../hooks/useJobs"
import { useHealth } from "../hooks/useHealth"
import KpiCard from "../components/KpiCard"
import StatusBadge from "../components/StatusBadge"
import PhaseBar from "../components/PhaseBar"
import type { Job } from "../types"

const TERMINAL_STATUSES = new Set(["delivered", "published", "failed", "cancelled", "rejected"])
const VENTURE_OPTIONS = ["", "etsy", "marketing_audit", "content_studio"]
const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "running", label: "Running" },
  { value: "review_pending", label: "Review Pending" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
]
const PAGE_SIZE = 20

function SkeletonRow() {
  return (
    <tr>
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-surface-dim rounded animate-pulse" />
        </td>
      ))}
    </tr>
  )
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function formatCurrency(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n)
}

function HealthDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    healthy: "bg-emerald-500",
    ok: "bg-emerald-500",
    degraded: "bg-amber-400",
    down: "bg-error",
  }
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${colors[status] ?? "bg-slate-400"}`}
    />
  )
}

function InlineJobActions({ job }: { job: Job }) {
  const retry = useRetryJob()
  const cancel = useCancelJob()
  const [done, setDone] = useState<string | null>(null)

  if (done) {
    return <span className="text-xs font-label text-emerald-600">{done}</span>
  }

  return (
    <div className="flex items-center gap-2">
      <Link
        to={`/jobs/${job.id}`}
        className="text-xs font-label font-semibold text-primary hover:underline"
      >
        View
      </Link>
      {job.status === "failed" && (
        <button
          onClick={async () => {
            await retry.mutateAsync({ id: job.id })
            setDone("Retried")
          }}
          disabled={retry.isPending}
          className="text-xs font-label font-semibold text-amber-600 hover:underline disabled:opacity-50"
        >
          {retry.isPending ? "…" : "Retry"}
        </button>
      )}
      {!TERMINAL_STATUSES.has(job.status) && (
        <button
          onClick={async () => {
            await cancel.mutateAsync({ id: job.id })
            setDone("Cancelled")
          }}
          disabled={cancel.isPending}
          className="text-xs font-label font-semibold text-error hover:underline disabled:opacity-50"
        >
          {cancel.isPending ? "…" : "Cancel"}
        </button>
      )}
    </div>
  )
}

export default function Dashboard() {
  const { data: dash, isLoading: dashLoading, error: dashError } = useDashboard()
  const { data: health } = useHealth()

  // Filters for the jobs table
  const [ventureFilter, setVentureFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [page, setPage] = useState(1)

  const { data: jobsData, isLoading: jobsLoading } = useJobs({
    venture: ventureFilter || undefined,
    status: statusFilter || undefined,
    page,
    page_size: PAGE_SIZE,
  })

  // Review queue — always fetched separately so it isn't limited by the table's page/filter
  const { data: reviewData } = useJobs({ status: "review_pending", page_size: 50 })

  const activeJobs    = dash?.ventures.reduce((s, v) => s + v.in_progress + v.pending, 0) ?? 0
  const pendingReview = dash?.ventures.reduce((s, v) => s + v.pending_review, 0) ?? 0

  const kpis = [
    { label: "Active Jobs",       value: dashLoading ? "—" : String(activeJobs),                                icon: "bolt" },
    { label: "Pending Reviews",   value: dashLoading ? "—" : String(pendingReview),                             icon: "pending_actions" },
    { label: "Monthly Revenue",   value: dashLoading ? "—" : formatCurrency(dash?.total_revenue_usd_month ?? 0), icon: "payments" },
    { label: "API Spend",         value: dashLoading ? "—" : formatCurrency(dash?.total_cost_usd_month ?? 0),    icon: "account_balance_wallet" },
  ]

  const jobs: Job[] = jobsData?.items ?? []
  const totalJobs   = jobsData?.total ?? 0
  const totalPages  = Math.ceil(totalJobs / PAGE_SIZE)
  const reviewQueue: Job[] = reviewData?.items ?? []

  function resetPage() { setPage(1) }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-headline font-bold text-2xl text-on-surface">Dashboard</h1>
        <p className="text-sm font-body text-on-surface-variant mt-0.5">
          Platform overview — auto-refreshes every 30s
        </p>
      </div>

      {dashError && (
        <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px]">error</span>
          Failed to load dashboard: {(dashError as Error).message}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        {kpis.map((k) => (
          <KpiCard key={k.label} label={k.label} value={k.value} icon={k.icon} loading={dashLoading} />
        ))}
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Review Queue */}
        <div className="col-span-8 bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
          <div className="px-5 py-4 border-b border-outline-variant/15 flex items-center justify-between">
            <h2 className="font-headline font-bold text-base text-on-surface">Review Queue</h2>
            {reviewQueue.length > 0 && (
              <span className="bg-tertiary-fixed text-on-tertiary-fixed-variant text-[10px] font-bold uppercase px-2 py-0.5 rounded-full">
                {reviewQueue.length} waiting
              </span>
            )}
          </div>
          {reviewQueue.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm font-label text-on-surface-variant">
              No items pending review
            </div>
          ) : (
            <div className="divide-y divide-outline-variant/10">
              {reviewQueue.map((job: Job) => (
                <div
                  key={job.id}
                  className="px-5 py-3.5 flex items-center justify-between hover:bg-surface-container-low/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <StatusBadge status={job.status} />
                    <div>
                      <p className="text-sm font-label font-medium text-on-surface">
                        {job.venture.replace(/_/g, " ")}
                      </p>
                      <p className="text-xs text-on-surface-variant">
                        {job.id.slice(0, 8)}… &middot; {formatDate(job.created_at)}
                      </p>
                    </div>
                  </div>
                  <Link
                    to={`/jobs/${job.id}`}
                    className="text-xs font-label font-semibold text-primary hover:underline"
                  >
                    Review →
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* System Health */}
        <div className="col-span-4 bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
          <div className="px-5 py-4 border-b border-outline-variant/15 flex items-center justify-between">
            <h2 className="font-headline font-bold text-base text-on-surface">System Health</h2>
            {health && <HealthDot status={health.status} />}
          </div>
          <div className="px-5 py-3 space-y-3">
            {health ? (
              <>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HealthDot status={health.db ? "healthy" : "down"} />
                    <span className="text-sm font-label text-on-surface">Database</span>
                  </div>
                  <span className="text-xs font-label text-on-surface-variant">
                    {health.db ? "Connected" : "Down"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HealthDot status={health.redis ? "healthy" : "down"} />
                    <span className="text-sm font-label text-on-surface">Redis</span>
                  </div>
                  <span className="text-xs font-label text-on-surface-variant">
                    {health.redis ? "Connected" : "Down"}
                  </span>
                </div>
                {dash && (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <HealthDot status={dash.db_ok ? "healthy" : "down"} />
                      <span className="text-sm font-label text-on-surface">API</span>
                    </div>
                    <span className="text-xs font-label text-on-surface-variant">
                      v{health.version}
                    </span>
                  </div>
                )}
              </>
            ) : (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center justify-between">
                    <div className="h-4 w-24 bg-surface-dim rounded animate-pulse" />
                    <div className="h-4 w-12 bg-surface-dim rounded animate-pulse" />
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="px-5 py-3 border-t border-outline-variant/10">
            <Link
              to="/settings?tab=environment"
              className="text-xs font-label font-semibold text-primary hover:underline flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-[14px]">open_in_new</span>
              Full health report
            </Link>
          </div>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
        {/* Table header + filters */}
        <div className="px-5 py-4 border-b border-outline-variant/15 flex items-center gap-4 flex-wrap">
          <h2 className="font-headline font-bold text-base text-on-surface shrink-0">Job History</h2>

          {/* Venture filter */}
          <select
            value={ventureFilter}
            onChange={(e) => { setVentureFilter(e.target.value); resetPage() }}
            className="px-3 py-1.5 text-xs font-label bg-surface-container-low rounded-lg border border-transparent focus:border-primary/40 focus:outline-none text-on-surface"
          >
            <option value="">All ventures</option>
            {VENTURE_OPTIONS.filter(Boolean).map((v) => (
              <option key={v} value={v}>{v.replace(/_/g, " ")}</option>
            ))}
          </select>

          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); resetPage() }}
            className="px-3 py-1.5 text-xs font-label bg-surface-container-low rounded-lg border border-transparent focus:border-primary/40 focus:outline-none text-on-surface"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <span className="ml-auto text-xs font-label text-on-surface-variant">
            {totalJobs} jobs
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-container-low border-b border-outline-variant/10">
                {["Job ID", "Venture", "Status", "Phase", "Started", "Actions"].map((h) => (
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
              {jobsLoading && !jobs.length
                ? Array(5).fill(null).map((_, i) => <SkeletonRow key={i} />)
                : jobs.map((job) => (
                    <tr key={job.id} className="hover:bg-surface-container-low/40 transition-colors">
                      <td className="px-4 py-3 font-label text-xs text-on-surface-variant font-mono">
                        {job.id.slice(0, 8)}…
                      </td>
                      <td className="px-4 py-3 text-sm font-label text-on-surface capitalize">
                        {job.venture.replace(/_/g, " ")}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={job.status} />
                      </td>
                      <td className="px-4 py-3 min-w-[120px]">
                        <PhaseBar current={job.phase_current} total={job.phase_total} />
                      </td>
                      <td className="px-4 py-3 text-xs font-label text-on-surface-variant">
                        {job.started_at ? formatDate(job.started_at) : formatDate(job.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <InlineJobActions job={job} />
                      </td>
                    </tr>
                  ))}
              {!jobsLoading && jobs.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm font-label text-on-surface-variant">
                    No jobs match the current filters
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-5 py-3 border-t border-outline-variant/10 flex items-center justify-between">
            <span className="text-xs font-label text-on-surface-variant">
              Page {page} of {totalPages}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 text-xs font-label font-semibold text-on-surface-variant bg-surface-container-low rounded-lg disabled:opacity-40 hover:bg-surface-dim transition-colors"
              >
                ← Prev
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1 text-xs font-label font-semibold text-on-surface-variant bg-surface-container-low rounded-lg disabled:opacity-40 hover:bg-surface-dim transition-colors"
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
