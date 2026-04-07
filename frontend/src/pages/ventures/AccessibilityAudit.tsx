import { useState } from "react"
import { useQuery, useMutation } from "@tanstack/react-query"
import { fetchAccessibilityAudits, createAccessibilityAudit } from "../../api"

type Tab = "overview" | "new_order" | "orders"

const TIERS = [
  { id: "standard", label: "Standard Audit", price: "$120", description: "Up to 5 key user journeys with detailed PDF" },
  { id: "premium", label: "Premium + Strategy", price: "$250", description: "Complete site with 30-day remediation roadmap" },
] as const

function formatDate(iso: string | null | undefined) {
  if (!iso) return ""
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
      <div className="grid grid-cols-2 gap-4">
        {TIERS.map((t) => (
          <div key={t.id} className="bg-surface-container-lowest rounded-xl p-5 shadow-float">
            <div className="font-headline font-bold text-2xl text-primary mb-1">{t.price}</div>
            <div className="font-label font-semibold text-base text-on-surface mb-1">{t.label}</div>
            <div className="text-sm font-body text-on-surface-variant">{t.description}</div>
          </div>
        ))}
      </div>
      <div className="bg-surface-container-lowest rounded-xl p-5 shadow-float border border-outline-variant/20">
        <h3 className="font-headline font-bold text-base text-on-surface mb-2">Public Sample Offer</h3>
        <p className="text-sm font-body text-on-surface-variant">
          The one-page sample audit is still supported for website lead-gen flows, but it is no longer exposed in the internal admin ordering UI.
        </p>
      </div>
      <div className="bg-surface-container-lowest rounded-xl p-5 shadow-float">
        <h3 className="font-headline font-bold text-base text-on-surface mb-3">Pipeline Phases</h3>
        <div className="grid grid-cols-5 gap-2">
          {[
            "Initiate",
            "Headless Scan",
            "Create Report",
            "Human Review",
            "Client Delivery",
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

function NewOrder({ onSuccess }: { onSuccess: () => void }) {
  const [url, setUrl] = useState("")
  const [tier, setTier] = useState<"standard" | "premium">("standard")
  const [clientEmail, setClientEmail] = useState("")
  const [isDemo, setIsDemo] = useState(false)
  const [errorMsg, setErrorMsg] = useState("")

  const submitMut = useMutation({
    mutationFn: createAccessibilityAudit,
    onSuccess: (data) => {
      console.log("Ordered Audit successfully", data)
      onSuccess()
    },
    onError: (err: any) => setErrorMsg(err.message || String(err)),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErrorMsg("")
    submitMut.mutate({
      url,
      tier,
      client_email: clientEmail || undefined,
      is_testing: isDemo,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="card p-6 max-w-2xl">
      <h2 className="font-headline font-bold text-xl mb-4">New Accessibility Audit Order</h2>
      
      {errorMsg && (
        <div className="bg-error/10 text-error p-3 rounded-lg text-sm mb-4">
          {errorMsg}
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-label font-bold text-on-surface mb-1">Target URL</label>
          <input
            required
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com"
            className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2"
          />
        </div>

        <div>
          <label className="block text-sm font-label font-bold text-on-surface mb-1">Package Tier</label>
          <select
            value={tier}
            onChange={(e) => setTier(e.target.value as typeof tier)}
            className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2"
          >
            {TIERS.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label} ({t.price})
              </option>
            ))}
          </select>
        </div>

        <div>
           <label className="block text-sm font-label font-bold text-on-surface mb-1">Client Email (Optional)</label>
           <input
             type="email"
             value={clientEmail}
             onChange={(e) => setClientEmail(e.target.value)}
             placeholder="client@company.com"
             className="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2"
           />
        </div>

        <label className="flex items-center gap-2 cursor-pointer bg-surface-container-lowest p-3 rounded-lg border border-outline-variant/30">
          <input 
            type="checkbox" 
            checked={isDemo}
            onChange={(e) => setIsDemo(e.target.checked)}
            className="w-4 h-4 text-primary bg-surface border-outline-variant/30 rounded focus:ring-primary focus:ring-offset-surface"
          />
          <div className="flex-1">
            <span className="font-label font-bold text-on-surface text-sm block">Demo Mode (No Revenue Tracked)</span>
            <span className="text-xs text-on-surface-variant font-body">Use this to test the pipeline. The cost of APIs is still tracked, but revenue is bypassed.</span>
          </div>
        </label>
      </div>

      <div className="mt-8 flex justify-end">
        <button
          type="submit"
          disabled={submitMut.isPending}
          className="btn-primary py-2 px-6 shadow-float"
        >
          {submitMut.isPending ? "Submitting..." : "Start Audit"}
        </button>
      </div>
    </form>
  )
}

function OrdersList() {
  const { data: items, isLoading, refetch } = useQuery({
    queryKey: ["aam-orders"],
    queryFn: () => fetchAccessibilityAudits(),
    refetchInterval: 10000,
  })

  if (isLoading) return <div className="text-on-surface-variant animate-pulse">Loading audits...</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-headline font-bold text-lg text-on-surface">Recent Audits</h2>
        <button onClick={() => refetch()} className="btn bg-surface-variant hover:bg-surface-container text-xs px-3 py-1">
          Refresh
        </button>
      </div>

      <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/20 overflow-hidden">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-surface border-b border-outline-variant/20 font-label">
            <tr>
              <th className="px-4 py-3 font-semibold text-on-surface-variant">URL</th>
              <th className="px-4 py-3 font-semibold text-on-surface-variant">Status</th>
              <th className="px-4 py-3 font-semibold text-on-surface-variant">Score</th>
              <th className="px-4 py-3 font-semibold text-on-surface-variant text-right">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/10 font-body">
            {items?.map((item: any) => (
              <tr key={item.id} className="hover:bg-surface/50 transition-colors">
                <td className="px-4 py-3 font-medium cursor-pointer text-primary hover:underline">{item.url}</td>
                <td className="px-4 py-3">
                   {item.status}
                </td>
                <td className="px-4 py-3">
                   {item.score !== null ? item.score : "-"}
                </td>
                <td className="px-4 py-3 text-right text-on-surface-variant">
                  {formatDate(item.created_at)}
                </td>
              </tr>
            ))}
            {(!items || items.length === 0) && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-on-surface-variant">
                  No audits found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function AccessibilityAudit() {
  const [tab, setTab] = useState<Tab>("overview")

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      <div>
        <div className="flex items-center gap-3 mb-1">
          <span className="material-symbols-outlined text-primary text-3xl">accessibility_new</span>
          <h1 className="text-2xl font-black font-headline tracking-tight text-on-surface">
            Accessibility Audit
          </h1>
        </div>
        <p className="text-sm text-on-surface-variant">
          WCAG 2.1 automated heuristic scanning and issue extraction
        </p>
      </div>

      <div className="flex gap-2 border-b border-outline-variant/20 pb-[1px]">
        {[
          { id: "overview", label: "Overview", icon: "dashboard" },
          { id: "new_order", label: "New Order", icon: "add_circle" },
          { id: "orders", label: "Orders", icon: "list_alt" },
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
        {tab === "new_order" && <NewOrder onSuccess={() => setTab("orders")} />}
        {tab === "orders" && <OrdersList />}
      </div>
    </div>
  )
}

