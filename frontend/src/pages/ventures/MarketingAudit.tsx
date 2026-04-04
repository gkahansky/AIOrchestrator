import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery, useMutation } from "@tanstack/react-query"
import { fetchAuditOrders, createAuditOrder } from "../../api"
import StatusBadge from "../../components/StatusBadge"
import PhaseBar from "../../components/PhaseBar"
import type { AuditOrderRequest } from "../../types"

type Tab = "overview" | "new_order" | "orders"

const TIERS = [
  { id: "snapshot", label: "Snapshot", price: "$49", description: "Quick SEO health check" },
  { id: "full", label: "Full Audit", price: "$149", description: "Complete site analysis" },
  { id: "premium", label: "Audit + Strategy", price: "$249", description: "Audit with 90-day action plan" },
] as const

const REPORT_TYPES = [
  { id: "both", label: "Full + Sample" },
  { id: "full", label: "Full Only" },
  { id: "sample", label: "Sample Only" },
] as const

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
      <div className="grid grid-cols-3 gap-4">
        {TIERS.map((t) => (
          <div key={t.id} className="bg-surface-container-lowest rounded-xl p-5 shadow-float">
            <div className="font-headline font-bold text-2xl text-primary mb-1">{t.price}</div>
            <div className="font-label font-semibold text-base text-on-surface mb-1">{t.label}</div>
            <div className="text-sm font-body text-on-surface-variant">{t.description}</div>
          </div>
        ))}
      </div>
      <div className="bg-surface-container-lowest rounded-xl p-5 shadow-float">
        <h3 className="font-headline font-bold text-base text-on-surface mb-3">Pipeline Phases</h3>
        <div className="grid grid-cols-5 gap-2">
          {[
            "Scrape",
            "Audit",
            "Generate Report",
            "Review",
            "Deliver",
          ].map((phase, i) => (
            <div key={i} className="text-center">
              <div className="w-8 h-8 rounded-full bg-primary-fixed flex items-center justify-center mx-auto mb-1">
                <span className="text-xs font-label font-bold text-on-primary-fixed-variant">
                  {i + 1}
                </span>
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
  const [form, setForm] = useState<AuditOrderRequest>({
    url: "",
    tier: "snapshot",
    client_email: "",
    report_type: "both",
  })
  const [errors, setErrors] = useState<Partial<Record<keyof AuditOrderRequest, string>>>({})

  const mutation = useMutation({
    mutationFn: createAuditOrder,
    onSuccess: (data) => {
      navigate(`/jobs/${data.job_id}`)
    },
  })

  function validate() {
    const e: typeof errors = {}
    if (!form.url.trim()) e.url = "URL is required"
    else {
      try {
        new URL(form.url)
      } catch {
        e.url = "Must be a valid URL"
      }
    }
    if (!(form.client_email ?? "").trim()) e.client_email = "Client email is required"
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.client_email ?? ""))
      e.client_email = "Must be a valid email"
    return e
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length > 0) {
      setErrors(errs)
      return
    }
    setErrors({})
    mutation.mutate(form)
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-xl space-y-6">
      {/* URL */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          Website URL <span className="text-error">*</span>
        </label>
        <input
          type="text"
          value={form.url}
          onChange={(e) => setForm({ ...form, url: e.target.value })}
          placeholder="https://example.com"
          className={`w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border ${
            errors.url ? "border-error" : "border-transparent"
          } focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors`}
        />
        {errors.url && <p className="text-xs text-error mt-1 font-label">{errors.url}</p>}
      </div>

      {/* Tier */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-2 uppercase tracking-wider">
          Audit Tier <span className="text-error">*</span>
        </label>
        <div className="space-y-2">
          {TIERS.map((t) => (
            <label
              key={t.id}
              className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-colors ${
                form.tier === t.id
                  ? "bg-primary-fixed border border-primary/20"
                  : "bg-surface-container-low border border-transparent hover:bg-surface-container"
              }`}
            >
              <input
                type="radio"
                name="tier"
                value={t.id}
                checked={form.tier === t.id}
                onChange={() => setForm({ ...form, tier: t.id })}
                className="accent-primary"
              />
              <div className="flex-1">
                <span className="text-sm font-label font-medium text-on-surface">{t.label}</span>
                <span className="text-xs text-on-surface-variant ml-2">{t.description}</span>
              </div>
              <span className="text-sm font-label font-bold text-primary">{t.price}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Client Email */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
          Client Email <span className="text-error">*</span>
        </label>
        <input
          type="email"
          value={form.client_email}
          onChange={(e) => setForm({ ...form, client_email: e.target.value })}
          placeholder="client@example.com"
          className={`w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border ${
            errors.client_email ? "border-error" : "border-transparent"
          } focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors`}
        />
        {errors.client_email && (
          <p className="text-xs text-error mt-1 font-label">{errors.client_email}</p>
        )}
      </div>

      {/* Report Type */}
      <div>
        <label className="block text-xs font-label font-medium text-on-surface-variant mb-2 uppercase tracking-wider">
          Report Type
        </label>
        <div className="flex gap-2">
          {REPORT_TYPES.map((rt) => (
            <label
              key={rt.id}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl cursor-pointer text-sm font-label transition-colors ${
                form.report_type === rt.id
                  ? "bg-primary-fixed text-on-primary-fixed-variant font-semibold"
                  : "bg-surface-container-low text-on-surface-variant hover:bg-surface-container"
              }`}
            >
              <input
                type="radio"
                name="report_type"
                value={rt.id}
                checked={form.report_type === rt.id}
                onChange={() => setForm({ ...form, report_type: rt.id })}
                className="sr-only"
              />
              {rt.label}
            </label>
          ))}
        </div>
      </div>

      {mutation.error && (
        <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label">
          {(mutation.error as Error).message}
        </div>
      )}

      <button
        type="submit"
        disabled={mutation.isPending}
        className="w-full py-3 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary text-sm font-label font-semibold shadow-float hover:opacity-90 transition-opacity disabled:opacity-60"
      >
        {mutation.isPending ? "Creating Order…" : "Create Order"}
      </button>
    </form>
  )
}

function OrdersList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["auditOrders"],
    queryFn: () => fetchAuditOrders({ page_size: 50 }),
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
              {["Job ID", "URL", "Tier", "Status", "Phase", "Created", "Actions"].map((h) => (
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
              ? Array(5)
                  .fill(null)
                  .map((_, i) => (
                    <tr key={i}>
                      {Array(7)
                        .fill(null)
                        .map((__, j) => (
                          <td key={j} className="px-4 py-3">
                            <div className="h-4 bg-surface-dim rounded animate-pulse" />
                          </td>
                        ))}
                    </tr>
                  ))
              : data?.items.map((job) => (
                  <tr
                    key={job.id}
                    className="hover:bg-surface-container-low/40 transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">
                      {job.id.slice(0, 8)}…
                    </td>
                    <td className="px-4 py-3 text-sm font-label text-on-surface max-w-[200px] truncate">
                      {(job.input_data.url as string) ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-sm font-label text-on-surface capitalize">
                      {(job.input_data.tier as string)?.replace(/_/g, " ") ?? "—"}
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
                      <button
                        onClick={() => navigate(`/jobs/${job.id}`)}
                        className="text-xs font-label font-semibold text-primary hover:underline"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
            {!isLoading && data?.items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-sm font-label text-on-surface-variant">
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

export default function MarketingAudit() {
  const [tab, setTab] = useState<Tab>("overview")

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "new_order", label: "New Order" },
    { id: "orders", label: "Orders" },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="material-symbols-outlined text-[24px] text-tertiary">search</span>
            <h1 className="font-headline font-bold text-2xl text-on-surface">Marketing Audit</h1>
          </div>
          <p className="text-sm font-body text-on-surface-variant">
            EchoForge — website SEO & marketing audit service
          </p>
        </div>
        <button
          onClick={() => setTab("new_order")}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary text-sm font-label font-semibold shadow-float hover:opacity-90 transition-opacity"
        >
          <span className="material-symbols-outlined text-[16px]">add</span>
          New Order
        </button>
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

      {/* Content */}
      {tab === "overview" && <Overview />}
      {tab === "new_order" && <NewOrderForm />}
      {tab === "orders" && <OrdersList />}
    </div>
  )
}
