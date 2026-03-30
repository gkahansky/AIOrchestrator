import type { JobStatus } from "../types"

interface Props {
  status: JobStatus | string
}

function getClasses(status: string): string {
  const base = "px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-wide inline-block"

  switch (status) {
    case "pending":
      return `${base} bg-slate-100 text-slate-600`

    case "scraping":
    case "transcribing":
    case "generating":
    case "generating_report":
    case "packaging":
    case "delivering":
    case "auditing":
      return `${base} bg-blue-50 text-blue-700`

    case "scraped":
    case "transcribed":
    case "generated":
    case "packaged":
    case "audited":
    case "report_ready":
      return `${base} bg-blue-100 text-blue-800`

    case "review_pending":
      return `${base} bg-[#f2daff] text-[#6a0baa]`

    case "delivered":
    case "published":
    case "completed":
      return `${base} bg-emerald-100 text-emerald-700`

    case "failed":
      return `${base} bg-[#ffdad6] text-[#ba1a1a]`

    case "approved":
      return `${base} bg-[#d9e2ff] text-[#00429c]`

    default:
      return `${base} bg-slate-100 text-slate-500`
  }
}

function getLabel(status: string): string {
  return status.replace(/_/g, " ")
}

export default function StatusBadge({ status }: Props) {
  return <span className={getClasses(status)}>{getLabel(status)}</span>
}
