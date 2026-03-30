import { Link } from "react-router-dom"
import { useDashboard } from "../hooks/useDashboard"
import { useJobs } from "../hooks/useJobs"
import { useHealth } from "../hooks/useHealth"
import KpiCard from "../components/KpiCard"
import StatusBadge from "../components/StatusBadge"
import PhaseBar from "../components/PhaseBar"
import type { Job } from "../types"

function SkeletonRow() {
  return (
    <tr>
      {[1, 2, 3, 4, 5].map((i) => (
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
    degraded: "bg-amber-400",
    down: "bg-error",
  }
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${colors[status] ?? "bg-slate-400"}`}
    />
  )
}

export default function Dashboard() {
  const { data: dash, isLoading: dashLoading, error: dashError } = useDashboard()
  const { data: jobsData, isLoading: jobsLoading } = useJobs({ page_size: 10 })
  const { data: health } = useHealth()

  const kpis = [
    {
      label: "Active Jobs",
      value: dashLoading ? "—" : String(dash?.active_jobs ?? 0),
      icon: "bolt",
    },
    {
      label: "Pending Reviews",
      value: dashLoading ? "—" : String(dash?.pending_reviews ?? 0),
      icon: "pending_actions",
    },
    {
      label: "Monthly Revenue",
      value: dashLoading ? "—" : formatCurrency(dash?.monthly_revenue ?? 0),
      icon: "payments",
    },
    {
      label: "API Spend",
      value: dashLoading ? "—" : formatCurrency(dash?.api_spend ?? 0),
      icon: "account_balance_wallet",
    },
  ]

  const jobs: Job[] = dash?.jobs_in_flight ?? jobsData?.items ?? []
  const reviewQueue: Job[] = dash?.review_queue ?? []

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
          {reviewQueue.length === 0 && !dashLoading ? (
            <div className="px-5 py-8 text-center text-sm font-label text-on-surface-variant">
              No items pending review
            </div>
          ) : (
            <div className="divide-y divide-outline-variant/10">
              {(dashLoading ? Array(3).fill(null) : reviewQueue).map((job: Job | null, i: number) =>
                job ? (
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
                ) : (
                  <div key={i} className="px-5 py-3.5">
                    <div className="h-4 w-48 bg-surface-dim rounded animate-pulse" />
                  </div>
                )
              )}
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
            {health?.services ? (
              health.services.map((svc) => (
                <div key={svc.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HealthDot status={svc.status} />
                    <span className="text-sm font-label text-on-surface">{svc.name}</span>
                  </div>
                  <span className="text-xs font-label text-on-surface-variant">
                    {svc.latency_ms != null ? `${svc.latency_ms}ms` : svc.status}
                  </span>
                </div>
              ))
            ) : (
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
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

      {/* Jobs in Flight */}
      <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
        <div className="px-5 py-4 border-b border-outline-variant/15">
          <h2 className="font-headline font-bold text-base text-on-surface">Jobs in Flight</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-container-low border-b border-outline-variant/10">
                <th className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                  Job ID
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                  Venture
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                  Status
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                  Phase
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                  Started
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/10">
              {jobsLoading && !jobs.length
                ? Array(5)
                    .fill(null)
                    .map((_, i) => <SkeletonRow key={i} />)
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
                        {job.started_at ? formatDate(job.started_at) : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          to={`/jobs/${job.id}`}
                          className="text-xs font-label font-semibold text-primary hover:underline"
                        >
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
              {!jobsLoading && jobs.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-sm font-label text-on-surface-variant"
                  >
                    No active jobs
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
