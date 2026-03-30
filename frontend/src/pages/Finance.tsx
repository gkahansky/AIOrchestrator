import { useFinance } from "../hooks/useFinance"

function formatCurrency(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n)
}

function formatPct(n: number) {
  return `${n.toFixed(1)}%`
}

export default function Finance() {
  const { data, isLoading, error } = useFinance()

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-headline font-bold text-2xl text-on-surface">Finance</h1>
        <p className="text-sm font-body text-on-surface-variant mt-0.5">
          Revenue, costs, and P&amp;L summary
        </p>
      </div>

      {error && (
        <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px]">error</span>
          Failed to load finance data: {(error as Error).message}
        </div>
      )}

      {/* P&L Summary */}
      <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
        <div className="px-5 py-4 border-b border-outline-variant/15">
          <h2 className="font-headline font-bold text-base text-on-surface">P&amp;L Summary</h2>
          {data?.pnl.period && (
            <p className="text-xs font-label text-on-surface-variant mt-0.5">{data.pnl.period}</p>
          )}
        </div>
        <div className="grid grid-cols-4 divide-x divide-outline-variant/10">
          {isLoading ? (
            Array(4)
              .fill(null)
              .map((_, i) => (
                <div key={i} className="px-6 py-5">
                  <div className="h-3 w-20 bg-surface-dim rounded animate-pulse mb-2" />
                  <div className="h-7 w-28 bg-surface-dim rounded animate-pulse" />
                </div>
              ))
          ) : (
            <>
              <div className="px-6 py-5">
                <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">
                  Gross Revenue
                </p>
                <p className="text-2xl font-headline font-bold text-on-surface">
                  {formatCurrency(data?.pnl.gross_revenue ?? 0)}
                </p>
              </div>
              <div className="px-6 py-5">
                <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">
                  Total Costs
                </p>
                <p className="text-2xl font-headline font-bold text-on-surface">
                  {formatCurrency(data?.pnl.total_costs ?? 0)}
                </p>
              </div>
              <div className="px-6 py-5">
                <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">
                  Net Profit
                </p>
                <p
                  className={`text-2xl font-headline font-bold ${
                    (data?.pnl.net_profit ?? 0) >= 0 ? "text-emerald-600" : "text-error"
                  }`}
                >
                  {formatCurrency(data?.pnl.net_profit ?? 0)}
                </p>
              </div>
              <div className="px-6 py-5">
                <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">
                  Margin
                </p>
                <p
                  className={`text-2xl font-headline font-bold ${
                    (data?.pnl.margin_pct ?? 0) >= 0 ? "text-emerald-600" : "text-error"
                  }`}
                >
                  {formatPct(data?.pnl.margin_pct ?? 0)}
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Revenue by Venture */}
        <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
          <div className="px-5 py-4 border-b border-outline-variant/15">
            <h2 className="font-headline font-bold text-base text-on-surface">Revenue by Venture</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant/10">
                  <th className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                    Venture
                  </th>
                  <th className="px-4 py-2.5 text-right text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                    Orders
                  </th>
                  <th className="px-4 py-2.5 text-right text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                    Revenue
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {isLoading
                  ? Array(3)
                      .fill(null)
                      .map((_, i) => (
                        <tr key={i}>
                          {[1, 2, 3].map((j) => (
                            <td key={j} className="px-4 py-3">
                              <div className="h-4 bg-surface-dim rounded animate-pulse" />
                            </td>
                          ))}
                        </tr>
                      ))
                  : data?.revenue_by_venture.map((r) => (
                      <tr key={r.venture} className="hover:bg-surface-container-low/40 transition-colors">
                        <td className="px-4 py-3 text-sm font-label text-on-surface capitalize">
                          {r.venture.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-3 text-sm font-label text-on-surface text-right">
                          {r.order_count}
                        </td>
                        <td className="px-4 py-3 text-sm font-label font-semibold text-on-surface text-right">
                          {formatCurrency(r.total_revenue)}
                        </td>
                      </tr>
                    ))}
                {!isLoading && !data?.revenue_by_venture.length && (
                  <tr>
                    <td
                      colSpan={3}
                      className="px-4 py-6 text-center text-sm font-label text-on-surface-variant"
                    >
                      No revenue data
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Cost by Tool */}
        <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
          <div className="px-5 py-4 border-b border-outline-variant/15">
            <h2 className="font-headline font-bold text-base text-on-surface">Cost by Tool</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-container-low border-b border-outline-variant/10">
                  <th className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                    Tool
                  </th>
                  <th className="px-4 py-2.5 text-right text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                    Calls
                  </th>
                  <th className="px-4 py-2.5 text-right text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant">
                    Cost
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {isLoading
                  ? Array(4)
                      .fill(null)
                      .map((_, i) => (
                        <tr key={i}>
                          {[1, 2, 3].map((j) => (
                            <td key={j} className="px-4 py-3">
                              <div className="h-4 bg-surface-dim rounded animate-pulse" />
                            </td>
                          ))}
                        </tr>
                      ))
                  : data?.cost_by_tool.map((c) => (
                      <tr key={c.tool} className="hover:bg-surface-container-low/40 transition-colors">
                        <td className="px-4 py-3 text-sm font-label text-on-surface font-mono">
                          {c.tool}
                        </td>
                        <td className="px-4 py-3 text-sm font-label text-on-surface text-right">
                          {c.call_count.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-sm font-label font-semibold text-on-surface text-right">
                          {formatCurrency(c.total_cost)}
                        </td>
                      </tr>
                    ))}
                {!isLoading && !data?.cost_by_tool.length && (
                  <tr>
                    <td
                      colSpan={3}
                      className="px-4 py-6 text-center text-sm font-label text-on-surface-variant"
                    >
                      No cost data
                    </td>
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
