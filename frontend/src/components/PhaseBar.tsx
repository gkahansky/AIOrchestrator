interface Props {
  current: number | null
  total: number | null
  className?: string
}

export default function PhaseBar({ current, total, className = "" }: Props) {
  if (current === null || total === null || total === 0) {
    return (
      <span className={`text-xs text-on-surface-variant ${className}`}>—</span>
    )
  }

  const pct = Math.min(100, Math.round((current / total) * 100))

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="flex-1 h-1.5 bg-surface-dim rounded-full overflow-hidden min-w-[48px]">
        <div
          className="h-full bg-primary rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] font-label text-on-surface-variant whitespace-nowrap">
        {current}/{total}
      </span>
    </div>
  )
}
