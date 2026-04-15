import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  createSecurityAuditOrder,
  fetchSecurityAuditOrders,
  fetchSecurityAuditOrder,
  verifyScopeSecurityAudit,
  approveScopeSecurityAudit,
  reviewSecurityAuditOrder,
  deliverSecurityAuditOrder,
} from "../../api"

type Tab = "overview" | "new_order" | "orders" | "detail"

const TIERS = [
  {
    id: "starter",
    label: "Starter",
    price: "$49",
    description: "Black-box only. Phases 1–3: passive OSINT, surface mapping, header/TLS/CORS analysis.",
    turnaround: "< 4 hours",
  },
  {
    id: "professional",
    label: "Professional",
    price: "$149",
    description: "Grey-box with authenticated Playwright testing. Full attack chain analysis.",
    turnaround: "< 6 hours",
  },
  {
    id: "agency",
    label: "Agency",
    price: "$349",
    description: "Everything in Professional + multi-subdomain scope. White-label available.",
    turnaround: "< 3 hours",
  },
] as const

const SEVERITY_COLORS: Record<string, string> = {
  Critical: "text-red-600 bg-red-50",
  High: "text-orange-500 bg-orange-50",
  Medium: "text-yellow-600 bg-yellow-50",
  Low: "text-green-600 bg-green-50",
  Informational: "text-blue-500 bg-blue-50",
}

const STATUS_COLORS: Record<string, string> = {
  scope_pending: "text-yellow-600 bg-yellow-50",
  scope_verified: "text-blue-500 bg-blue-50",
  scanning: "text-purple-600 bg-purple-50",
  correlating: "text-purple-600 bg-purple-50",
  review_pending: "text-orange-500 bg-orange-50",
  approved: "text-green-600 bg-green-50",
  delivering: "text-blue-500 bg-blue-50",
  delivered: "text-green-700 bg-green-100",
  failed: "text-red-600 bg-red-50",
  rejected: "text-red-600 bg-red-50",
}

function formatDate(iso: string | null | undefined) {
  if (!iso) return ""
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  })
}

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] || "text-on-surface-variant bg-surface-container"
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-label font-bold uppercase tracking-wide ${cls}`}>
      {status.replace(/_/g, " ")}
    </span>
  )
}

// ── Overview ──────────────────────────────────────────────────────────────────

function Overview() {
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-3 gap-4">
        {TIERS.map((t) => (
          <div key={t.id} className="bg-surface-container-lowest rounded-xl p-5 shadow-float border border-outline-variant/20">
            <div className="font-headline font-bold text-2xl text-primary mb-1">{t.price}</div>
            <div className="font-label font-semibold text-base text-on-surface mb-1">{t.label}</div>
            <div className="text-xs font-body text-on-surface-variant mb-2">{t.description}</div>
            <div className="text-[10px] font-label uppercase tracking-widest text-outline">
              Turnaround: {t.turnaround}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-surface-container-lowest rounded-xl p-6 shadow-float border border-outline-variant/20">
        <h3 className="font-headline font-bold text-base text-on-surface mb-3">Pipeline Phases</h3>
        <div className="grid grid-cols-6 gap-2">
          {[
            ["1", "Passive OSINT", "DNS, crt.sh, Wayback, HIBP"],
            ["2", "Surface Mapping", "HTTP probing, exposed paths"],
            ["3", "Vuln Scan", "Headers, TLS, CORS, cookies"],
            ["4", "Exploitation", "PoC capture (Pro+)"],
            ["5", "Auth Testing", "Playwright authenticated (Pro+)"],
            ["6", "AI Correlation", "Claude → PDF report"],
          ].map(([num, title, sub]) => (
            <div key={num} className="text-center">
              <div className="w-9 h-9 rounded-full bg-primary-fixed flex items-center justify-center mx-auto mb-2">
                <span className="text-xs font-label font-bold text-on-primary-fixed-variant">{num}</span>
              </div>
              <p className="text-xs font-label font-semibold text-on-surface">{title}</p>
              <p className="text-[10px] font-body text-on-surface-variant mt-0.5">{sub}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-5">
        <div className="flex items-start gap-3">
          <span className="material-symbols-outlined text-yellow-600 text-xl">warning</span>
          <div>
            <h4 className="font-label font-bold text-sm text-yellow-800">Scope Verification Required</h4>
            <p className="text-xs text-yellow-700 mt-1 font-body">
              Every order requires DNS TXT record verification before scanning begins.
              After creating an order you'll receive a TXT record to add to your DNS.
              Click "Verify Scope" once the record is live.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── New Order ─────────────────────────────────────────────────────────────────

function NewOrder({ onSuccess }: { onSuccess: (auditId: string) => void }) {
  const [url, setUrl] = useState("")
  const [tier, setTier] = useState<"starter" | "professional" | "agency">("starter")
  const [clientEmail, setClientEmail] = useState("")
  const [isDemo, setIsDemo] = useState(false)
  const [errorMsg, setErrorMsg] = useState("")

  const submitMut = useMutation({
    mutationFn: createSecurityAuditOrder,
    onSuccess: (data) => onSuccess(data.audit_id),
    onError: (err: any) => setErrorMsg(err.message || String(err)),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErrorMsg("")
    submitMut.mutate({ url, tier, client_email: clientEmail || undefined, is_testing: isDemo })
  }

  return (
    <form onSubmit={handleSubmit} className="card p-6 max-w-2xl space-y-5">
      <h2 className="font-headline font-bold text-xl">New Security Audit Order</h2>

      {errorMsg && (
        <div className="bg-error/10 text-error p-3 rounded-lg text-sm">{errorMsg}</div>
      )}

      <div>
        <label className="block text-sm font-label font-bold text-on-surface mb-1">Target URL *</label>
        <input
          required type="url" value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com"
          className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2"
        />
        <p className="text-[10px] text-on-surface-variant mt-1 font-body">
          You must own or have written authorisation to test this domain.
        </p>
      </div>

      <div>
        <label className="block text-sm font-label font-bold text-on-surface mb-1">Package Tier</label>
        <div className="grid grid-cols-3 gap-3">
          {TIERS.map((t) => (
            <label
              key={t.id}
              className={`cursor-pointer rounded-lg border p-3 transition-colors ${
                tier === t.id
                  ? "border-primary bg-primary/5"
                  : "border-outline-variant/30 bg-surface hover:bg-surface-container-low"
              }`}
            >
              <input
                type="radio" name="tier" value={t.id} checked={tier === t.id}
                onChange={() => setTier(t.id as typeof tier)} className="sr-only"
              />
              <div className="font-label font-bold text-sm text-primary">{t.price}</div>
              <div className="font-label font-semibold text-xs text-on-surface mt-0.5">{t.label}</div>
              <div className="text-[10px] text-on-surface-variant mt-1">{t.turnaround}</div>
            </label>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-label font-bold text-on-surface mb-1">Client Email (optional)</label>
        <input
          type="email" value={clientEmail}
          onChange={(e) => setClientEmail(e.target.value)}
          placeholder="client@company.com"
          className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2"
        />
      </div>

      <label className="flex items-center gap-3 cursor-pointer bg-surface-container-lowest p-3 rounded-lg border border-outline-variant/30">
        <input
          type="checkbox" checked={isDemo} onChange={(e) => setIsDemo(e.target.checked)}
          className="w-4 h-4 text-primary rounded"
        />
        <div>
          <span className="font-label font-bold text-sm block">Demo Mode</span>
          <span className="text-[10px] text-on-surface-variant font-body">
            Skips revenue logging. Scan still runs fully — useful for testing.
          </span>
        </div>
      </label>

      <div className="flex justify-end">
        <button type="submit" disabled={submitMut.isPending} className="btn-primary py-2 px-6">
          {submitMut.isPending ? "Creating order…" : "Create Order"}
        </button>
      </div>
    </form>
  )
}

// ── Scope Verification Panel ──────────────────────────────────────────────────

function ScopeVerificationPanel({ auditId, onVerified }: { auditId: string; onVerified: () => void }) {
  const qc = useQueryClient()
  const { data: order, isLoading } = useQuery({
    queryKey: ["sec-audit", auditId],
    queryFn: () => fetchSecurityAuditOrder(auditId),
    refetchInterval: 5000,
  })

  const verifyMut = useMutation({
    mutationFn: () => verifyScopeSecurityAudit(auditId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["sec-audit", auditId] })
      qc.invalidateQueries({ queryKey: ["sec-audits"] })
      if (data.verified) onVerified()
    },
  })

  const manualMut = useMutation({
    mutationFn: () => approveScopeSecurityAudit(auditId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sec-audit", auditId] })
      qc.invalidateQueries({ queryKey: ["sec-audits"] })
      onVerified()
    },
  })

  if (isLoading) return <div className="animate-pulse text-on-surface-variant">Loading…</div>
  if (!order) return null

  if (order.scope_verified) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-xl p-5">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-green-600">check_circle</span>
          <span className="font-label font-bold text-green-800">Scope verified — scan is queued</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 space-y-3">
        <h3 className="font-label font-bold text-blue-900">Add this DNS TXT record</h3>
        <div className="bg-white rounded-lg p-3 font-mono text-xs text-on-surface border border-blue-100 break-all">
          {order.scope_dns_record}
        </div>
        <p className="text-xs text-blue-700 font-body">
          Add this record to your domain's DNS, then click Verify below.
          DNS changes can take up to 60 seconds to propagate.
        </p>
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => verifyMut.mutate()}
          disabled={verifyMut.isPending}
          className="btn-primary py-2 px-5"
        >
          {verifyMut.isPending ? "Checking DNS…" : "Verify Scope"}
        </button>
        <button
          onClick={() => manualMut.mutate()}
          disabled={manualMut.isPending}
          className="btn bg-surface-variant text-on-surface hover:bg-surface-container py-2 px-4 text-sm"
        >
          Manual Override (testing)
        </button>
      </div>

      {verifyMut.data && !verifyMut.data.verified && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-800">
          {verifyMut.data.reason}
        </div>
      )}
    </div>
  )
}

// ── Order Detail ─────────────────────────────────────────────────────────────

function OrderDetail({ auditId, onBack }: { auditId: string; onBack: () => void }) {
  const qc = useQueryClient()
  const { data: order, isLoading } = useQuery({
    queryKey: ["sec-audit", auditId],
    queryFn: () => fetchSecurityAuditOrder(auditId),
    refetchInterval: 8000,
  })

  const reviewMut = useMutation({
    mutationFn: (action: "approve" | "reject") =>
      reviewSecurityAuditOrder(auditId, action, "Reviewed via admin UI"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sec-audit", auditId] }),
  })

  const deliverMut = useMutation({
    mutationFn: () => deliverSecurityAuditOrder(auditId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sec-audit", auditId] }),
  })

  if (isLoading) return <div className="animate-pulse text-on-surface-variant">Loading…</div>
  if (!order) return null

  const status = order.status
  const findings: any[] = order.findings || []
  const chains: any[] = order.attack_chains || []
  const outputData = order.output_data || {}

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="btn bg-surface-variant hover:bg-surface-container text-sm px-3 py-1.5">
          ← Back
        </button>
        <h2 className="font-headline font-bold text-lg text-on-surface truncate">
          {order.target_domain}
        </h2>
        <StatusBadge status={status} />
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-4 gap-4">
        {[
          ["Tier", order.tier?.toUpperCase()],
          ["Risk Score", order.risk_score != null ? `${order.risk_score}/100` : "—"],
          ["Risk Rating", outputData.risk_rating || "—"],
          ["Findings", `${findings.length} total`],
        ].map(([label, val]) => (
          <div key={label} className="bg-surface-container-lowest rounded-xl p-4 border border-surface-container">
            <div className="text-[9px] font-label uppercase tracking-widest text-outline">{label}</div>
            <div className="font-headline font-bold text-lg text-primary mt-1">{val}</div>
          </div>
        ))}
      </div>

      {/* Scope verification */}
      {(status === "scope_pending" || status === "scope_verified") && (
        <ScopeVerificationPanel auditId={auditId} onVerified={() =>
          qc.invalidateQueries({ queryKey: ["sec-audit", auditId] })
        } />
      )}

      {/* Scanning progress */}
      {["scanning", "correlating"].includes(status) && (
        <div className="bg-purple-50 border border-purple-200 rounded-xl p-5 flex items-center gap-3">
          <span className="material-symbols-outlined text-purple-600 animate-spin">refresh</span>
          <span className="font-label font-bold text-purple-800">
            {status === "scanning" ? "Scan in progress…" : "AI correlation in progress…"}
          </span>
        </div>
      )}

      {/* Drive link */}
      {outputData.drive_report_link && (
        <a
          href={outputData.drive_report_link}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 btn bg-primary text-white hover:bg-primary/90 py-2 px-4 w-fit"
        >
          <span className="material-symbols-outlined text-sm">open_in_new</span>
          View Report PDF
        </a>
      )}

      {/* Review gate */}
      {status === "review_pending" && (
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-5 space-y-3">
          <h3 className="font-label font-bold text-orange-800">Human Review Required</h3>
          <p className="text-xs text-orange-700 font-body">
            Review the report PDF above. Verify findings are genuine, PoC evidence is clear,
            and no out-of-scope hosts were probed.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => reviewMut.mutate("approve")}
              disabled={reviewMut.isPending}
              className="btn-primary py-2 px-5"
            >
              Approve
            </button>
            <button
              onClick={() => reviewMut.mutate("reject")}
              disabled={reviewMut.isPending}
              className="btn bg-error/10 text-error hover:bg-error/20 py-2 px-5"
            >
              Reject
            </button>
          </div>
        </div>
      )}

      {/* Deliver */}
      {status === "approved" && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-5 space-y-3">
          <h3 className="font-label font-bold text-green-800">Approved — Ready to Deliver</h3>
          <button
            onClick={() => deliverMut.mutate()}
            disabled={deliverMut.isPending}
            className="btn-primary py-2 px-5"
          >
            {deliverMut.isPending ? "Sending…" : "Send Report to Client"}
          </button>
        </div>
      )}

      {/* Findings */}
      {findings.length > 0 && (
        <div className="space-y-4">
          <h3 className="font-headline font-bold text-lg text-on-surface">
            Findings ({findings.length})
          </h3>
          <div className="grid grid-cols-2 gap-4">
            {findings.map((f: any, i: number) => {
              const sev = f.severity || "Low"
              const cls = SEVERITY_COLORS[sev] || ""
              return (
                <div key={i} className="bg-surface-container-lowest rounded-xl p-4 border border-surface-container space-y-2">
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${cls}`}>{sev}</span>
                    {f.cvss_score && (
                      <span className="text-xs font-label text-on-surface-variant">CVSS {f.cvss_score}</span>
                    )}
                  </div>
                  <p className="text-sm font-headline font-semibold text-primary">{f.title}</p>
                  {f.description && (
                    <p className="text-xs font-body text-on-surface-variant">{f.description}</p>
                  )}
                  {f.fix && (
                    <div>
                      <span className="text-[9px] font-label uppercase tracking-widest text-outline">Fix</span>
                      <p className="text-xs font-body text-on-surface mt-0.5">{f.fix}</p>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Attack chains */}
      {chains.length > 0 && (
        <div className="space-y-4">
          <h3 className="font-headline font-bold text-lg text-on-surface">Attack Chains</h3>
          <div className="space-y-3">
            {chains.map((c: any, i: number) => (
              <div key={i} className="bg-surface-container-lowest rounded-xl p-5 border border-surface-container">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-red-500 text-sm">warning</span>
                  <h4 className="font-headline font-bold text-primary">{c.title}</h4>
                  <span className={`text-xs font-bold ml-auto px-2 py-0.5 rounded-full ${SEVERITY_COLORS[c.severity] || ""}`}>
                    {c.severity}
                  </span>
                </div>
                <ol className="list-decimal list-inside space-y-1">
                  {(c.steps || []).map((s: string, j: number) => (
                    <li key={j} className="text-xs text-on-surface-variant font-body">{s}</li>
                  ))}
                </ol>
                {c.impact && (
                  <p className="text-xs italic text-on-surface-variant mt-2">{c.impact}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Orders List ───────────────────────────────────────────────────────────────

function OrdersList({ onSelectAudit }: { onSelectAudit: (id: string) => void }) {
  const { data: items, isLoading, refetch } = useQuery({
    queryKey: ["sec-audits"],
    queryFn: fetchSecurityAuditOrders,
    refetchInterval: 10000,
  })

  if (isLoading) return <div className="animate-pulse text-on-surface-variant">Loading…</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="font-headline font-bold text-lg text-on-surface">Recent Audits</h2>
        <button onClick={() => refetch()} className="btn bg-surface-variant hover:bg-surface-container text-xs px-3 py-1">
          Refresh
        </button>
      </div>
      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 overflow-hidden">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-surface border-b border-outline-variant/20 font-label">
            <tr>
              <th className="px-4 py-3 font-semibold text-on-surface-variant">Domain</th>
              <th className="px-4 py-3 font-semibold text-on-surface-variant">Tier</th>
              <th className="px-4 py-3 font-semibold text-on-surface-variant">Status</th>
              <th className="px-4 py-3 font-semibold text-on-surface-variant">Risk</th>
              <th className="px-4 py-3 font-semibold text-on-surface-variant">Findings</th>
              <th className="px-4 py-3 font-semibold text-on-surface-variant text-right">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/10 font-body">
            {items?.map((item: any) => (
              <tr
                key={item.audit_id}
                onClick={() => onSelectAudit(item.audit_id)}
                className="hover:bg-surface/50 cursor-pointer transition-colors"
              >
                <td className="px-4 py-3 font-medium text-primary hover:underline">{item.target_domain}</td>
                <td className="px-4 py-3 uppercase text-xs font-label">{item.tier}</td>
                <td className="px-4 py-3"><StatusBadge status={item.status} /></td>
                <td className="px-4 py-3">{item.risk_score != null ? `${item.risk_score}/100` : "—"}</td>
                <td className="px-4 py-3">{item.findings_count ?? "—"}</td>
                <td className="px-4 py-3 text-right text-on-surface-variant">{formatDate(item.created_at)}</td>
              </tr>
            ))}
            {(!items || items.length === 0) && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-on-surface-variant">No audits found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Root Component ────────────────────────────────────────────────────────────

export default function SecurityAudit() {
  const [tab, setTab] = useState<Tab>("overview")
  const [selectedAuditId, setSelectedAuditId] = useState<string | null>(null)
  const [pendingAuditId, setPendingAuditId] = useState<string | null>(null)

  function handleNewOrderSuccess(auditId: string) {
    setPendingAuditId(auditId)
    setSelectedAuditId(auditId)
    setTab("detail")
  }

  function handleSelectAudit(id: string) {
    setSelectedAuditId(id)
    setTab("detail")
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      <div>
        <div className="flex items-center gap-3 mb-1">
          <span className="material-symbols-outlined text-primary text-3xl">security</span>
          <h1 className="text-2xl font-black font-headline tracking-tight text-on-surface">
            Security Audit
          </h1>
        </div>
        <p className="text-sm text-on-surface-variant">
          OWASP-aligned black-box and grey-box web application security audits
        </p>
      </div>

      <div className="flex gap-2 border-b border-outline-variant/20 pb-[1px]">
        {[
          { id: "overview", label: "Overview", icon: "dashboard" },
          { id: "new_order", label: "New Order", icon: "add_circle" },
          { id: "orders", label: "Orders", icon: "list_alt" },
          ...(selectedAuditId ? [{ id: "detail", label: "Detail", icon: "article" }] : []),
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id as Tab)}
            className={`flex items-center gap-2 px-4 py-2 rounded-t-lg transition-colors font-label font-bold text-sm ${
              tab === t.id
                ? "bg-primary/10 text-primary border-b-2 border-primary"
                : "text-on-surface-variant hover:bg-surface-variant hover:text-on-surface"
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      <div className="animate-fade-in">
        {tab === "overview" && <Overview />}
        {tab === "new_order" && <NewOrder onSuccess={handleNewOrderSuccess} />}
        {tab === "orders" && <OrdersList onSelectAudit={handleSelectAudit} />}
        {tab === "detail" && selectedAuditId && (
          <OrderDetail
            auditId={selectedAuditId}
            onBack={() => setTab("orders")}
          />
        )}
      </div>
    </div>
  )
}
