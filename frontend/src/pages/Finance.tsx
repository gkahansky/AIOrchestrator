import { useFinance } from "../hooks/useFinance"

function formatCurrency(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n)
}

export default function Finance() {
  const { data, isLoading, error } = useFinance()

  // Compute P&L from the flat revenues/costs arrays the backend returns
  const grossRevenue  = data?.revenues.reduce((s, r) => s + r.total_amount_usd, 0) ?? 0
  const totalCosts    = data?.costs.reduce((s, c) => s + c.total_cost_usd, 0) ?? 0
  const netProfit     = data ? data.net_usd : 0
  const marginPct     = grossRevenue > 0 ? (netProfit / grossRevenue) * 100 : 0

  // Group revenues by venture
  const revenueByVenture = Object.values(
    (data?.revenues ?? []).reduce<Record<string, { venture: string; total: number; orders: number }>>(
      (acc, r) => {
        if (!acc[r.venture]) acc[r.venture] = { venture: r.venture, total: 0, orders: 0 }
        acc[r.venture].total  += r.total_net_usd
        acc[r.venture].orders += r.order_count
        return acc
      },
      {}
    )
  )

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-headline font-bold text-2xl text-on-surface">Finance</h1>
        <p className="text-sm font-body text-on-surface-variant mt-0.5">
          Revenue, costs, and P&amp;L — {data?.period ?? "current month"}
        </p>
      </div>

      {error && (
        <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px]">error</span>
          Failed to load finance data: {(error as Error).message}
        </div>
      )}

      {/* P&L Summary */}
      <div className="bg-surface-container-lowest rounded-xl overflow-hidden" style={{ boxShadow: "0px 20px 40px rgba(19,27,46,0.06)" }}>
        <div className="px-5 py-4 border-b border-outline-variant/15">
          <h2 className="font-headline font-bold text-base text-on-surface">P&amp;L Summary</h2>
          {data?.period && (
            <p className="text-xs font-label text-on-surface-variant mt-0.5">{data.period}</p>
          )}
        </div>
        <div className="grid grid-cols-4 divide-x divide-outline-variant/10">
          {isLoading ? (
            Array(4).fill(null).map((_, i) => (
              <div key={i} className="px-6 py-5">
                <div className="h-3 w-20 bg-surface-dim rounded animate-pulse mb-2" />
                <div className="h-7 w-28 bg-surface-dim rounded animate-pulse" />
              </div>
            ))
          ) : (
            <>
              <div className="px-6 py-5">
                <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">Gross Revenue</p>
                <p className="text-2xl font-headline font-bold text-on-surface">{formatCurrency(grossRevenue)}</p>
              </div>
              <div className="px-6 py-5">
                <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">Total Costs</p>
                <p className="text-2xl font-headline font-bold text-on-surface">{formatCurrency(totalCosts)}</p>
              </div>
              <div className="px-6 py-5">
                <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">Net Profit</p>
                <p className={`text-2xl font-headline font-bold ${netProfit >= 0 ? "text-emerald-600" : "text-error"}`}>
                  {formatCurrency(netProfit)}
                </p>
              </div>
              <div className="px-6 py-5">
                <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">Margin</p>
                <p className={`text-2xl font-headline font-bold ${marginPct >= 0 ? "text-emerald-600" : "text-error"}`}>
                  {marginPct.toFixed(1)}%
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Revenue by Venture */}
        <div className="bg-surface-container-lowest rounded-xl overflow-hidden" style={{ boxShadow: "0px 20px 40px rgba(19,27,46,0.06)" }}>
          <div className="px-5 py-4 border-b border-outline-variant/15">
            <h2 className="font-headline font-bold text-base text-on-surface">Revenue by Venture</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant/10">
                  {["Venture", "Orders", "Net Revenue"].map((h) => (
                    <th key={h} className={`px-4 py-2.5 text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant ${h !== "Venture" ? "text-right" : "text-left"}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {isLoading ? (
                  Array(3).fill(null).map((_, i) => (
                    <tr key={i}>{[1,2,3].map((j) => <td key={j} className="px-4 py-3"><div className="h-4 bg-surface-dim rounded animate-pulse" /></td>)}</tr>
                  ))
                ) : revenueByVenture.length > 0 ? (
                  revenueByVenture.map((r) => (
                    <tr key={r.venture} className="hover:bg-surface-container-low/40 transition-colors">
                      <td className="px-4 py-3 text-sm font-label text-on-surface capitalize">{r.venture.replace(/_/g, " ")}</td>
                      <td className="px-4 py-3 text-sm font-label text-on-surface text-right">{r.orders}</td>
                      <td className="px-4 py-3 text-sm font-label font-semibold text-on-surface text-right">{formatCurrency(r.total)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3} className="px-4 py-6 text-center text-sm font-label text-on-surface-variant">No revenue data yet</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Cost by Tool */}
        <div className="bg-surface-container-lowest rounded-xl overflow-hidden" style={{ boxShadow: "0px 20px 40px rgba(19,27,46,0.06)" }}>
          <div className="px-5 py-4 border-b border-outline-variant/15">
            <h2 className="font-headline font-bold text-base text-on-surface">Cost by Tool</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant/10">
                  {["Tool", "Capability", "Calls", "Total Cost"].map((h) => (
                    <th key={h} className={`px-4 py-2.5 text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant ${["Calls","Total Cost"].includes(h) ? "text-right" : "text-left"}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {isLoading ? (
                  Array(4).fill(null).map((_, i) => (
                    <tr key={i}>{[1,2,3,4].map((j) => <td key={j} className="px-4 py-3"><div className="h-4 bg-surface-dim rounded animate-pulse" /></td>)}</tr>
                  ))
                ) : data?.costs && data.costs.length > 0 ? (
                  data.costs.map((c) => (
                    <tr key={`${c.tool_id}-${c.capability}`} className="hover:bg-surface-container-low/40 transition-colors">
                      <td className="px-4 py-3 text-sm font-label text-on-surface font-mono">{c.tool_id}</td>
                      <td className="px-4 py-3 text-sm font-label text-on-surface-variant">{c.capability}</td>
                      <td className="px-4 py-3 text-sm font-label text-on-surface text-right">{c.call_count.toLocaleString()}</td>
                      <td className="px-4 py-3 text-sm font-label font-semibold text-on-surface text-right">{formatCurrency(c.total_cost_usd)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-sm font-label text-on-surface-variant">No cost data yet</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
