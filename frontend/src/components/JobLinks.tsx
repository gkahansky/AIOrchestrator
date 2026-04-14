/**
 * JobLinks — renders Open Document / Open Folder / Open Sample PDF buttons
 * from a job's output_data. Used in both order-list tables and JobDetail.
 *
 * Shows nothing if the output_data has no recognisable Drive links.
 */

interface JobLinksProps {
  outputData: Record<string, unknown>
  /** "inline" = compact icon+label buttons for table rows (default)
   *  "card"   = slightly larger buttons used in the detail page action bar */
  variant?: "inline" | "card"
}

function asString(v: unknown): string {
  return typeof v === "string" ? v : ""
}

export function extractJobLinks(outputData: Record<string, unknown>) {
  const candidates = [
    { label: "Open Document",   url: asString(outputData.drive_report_link),  icon: "description" },
    { label: "Open Folder",     url: asString(outputData.drive_folder_link),   icon: "folder_open" },
    { label: "Open Google Doc", url: asString(outputData.gdoc_url),            icon: "description" },
    { label: "Open Sample PDF", url: asString(outputData.drive_sample_pdf_link) || asString(outputData.drive_sample_PDF_link), icon: "picture_as_pdf" },
  ]
  const seen = new Set<string>()
  return candidates.filter(({ url }) => {
    if (!url || !/^https?:\/\//.test(url) || seen.has(url)) return false
    seen.add(url)
    return true
  })
}

export default function JobLinks({ outputData, variant = "inline" }: JobLinksProps) {
  const links = extractJobLinks(outputData)
  if (!links.length) return null

  if (variant === "inline") {
    return (
      <div className="flex flex-wrap gap-1.5">
        {links.map((link) => (
          <a
            key={link.url}
            href={link.url}
            target="_blank"
            rel="noreferrer"
            title={link.label}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-primary/10 text-primary text-[11px] font-label font-semibold hover:bg-primary/15 transition-colors whitespace-nowrap"
          >
            <span className="material-symbols-outlined text-[13px]">{link.icon}</span>
            {link.label}
          </a>
        ))}
      </div>
    )
  }

  // card variant
  return (
    <div className="flex flex-wrap gap-3">
      {links.map((link) => (
        <a
          key={link.url}
          href={link.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-primary/20 text-primary text-sm font-label font-semibold hover:bg-primary/5 transition-colors"
        >
          <span className="material-symbols-outlined text-[16px]">{link.icon}</span>
          {link.label}
        </a>
      ))}
    </div>
  )
}
