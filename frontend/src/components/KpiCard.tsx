interface Props {
  label: string
  value: string | number
  icon: string
  trend?: { value: string; positive: boolean }
  loading?: boolean
}

export default function KpiCard({ label, value, icon, trend, loading }: Props) {
  return (
    <div className="bg-surface-container-lowest rounded-xl p-5 shadow-float flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-label font-medium uppercase tracking-widest text-on-surface-variant">
          {label}
        </span>
        <span className="material-symbols-outlined text-[20px] text-primary">{icon}</span>
      </div>

      {loading ? (
        <div className="h-8 w-24 bg-surface-dim rounded animate-pulse" />
      ) : (
        <span className="text-3xl font-headline font-bold text-on-surface">{value}</span>
      )}

      {trend && !loading && (
        <span
          className={`text-xs font-label font-medium ${
            trend.positive ? "text-emerald-600" : "text-error"
          }`}
        >
          {trend.positive ? "▲" : "▼"} {trend.value}
        </span>
      )}
    </div>
  )
}
