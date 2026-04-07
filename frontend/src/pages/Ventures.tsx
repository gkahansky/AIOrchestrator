import { Link } from "react-router-dom"

interface VentureCard {
  name: string
  description: string
  to: string
  icon: string
  color: string
  bgColor: string
  status: "active" | "coming_soon"
}

const ventures: VentureCard[] = [
  {
    name: "Accessibility Audit",
    description: "EchoForge — automated WCAG scan & heuristic reporting",
    to: "/ventures/accessibility-audit",
    icon: "accessibility_new",
    color: "text-secondary",
    bgColor: "bg-surface-variant",
    status: "active",
  },
  {
    name: "Marketing Audit",
    description: "EchoForge — website SEO & marketing audit pipeline",
    to: "/ventures/marketing-audit",
    icon: "search",
    color: "text-primary",
    bgColor: "bg-primary-fixed",
    status: "active",
  },
  {
    name: "Content Studio",
    description: "EchoForge — podcast show notes & content repurposing",
    to: "/ventures/content-studio",
    icon: "mic",
    color: "text-tertiary",
    bgColor: "bg-tertiary-fixed",
    status: "active",
  },
  {
    name: "MiroPrintStudio",
    description: "Etsy digital image shop — AI-generated wall art",
    to: "/ventures/etsy",
    icon: "storefront",
    color: "text-on-surface-variant",
    bgColor: "bg-surface-container-high",
    status: "coming_soon",
  },
]

export default function Ventures() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-headline font-bold text-2xl text-on-surface">Ventures</h1>
        <p className="text-sm font-body text-on-surface-variant mt-0.5">
          Select a venture to manage orders and monitor pipelines
        </p>
      </div>

      <div className="grid grid-cols-3 gap-5">
        {ventures.map((v) => (
          <Link
            key={v.to}
            to={v.to}
            className="bg-surface-container-lowest rounded-xl p-6 shadow-float hover:shadow-float hover:-translate-y-0.5 transition-all group block"
          >
            <div className={`w-12 h-12 rounded-xl ${v.bgColor} flex items-center justify-center mb-4`}>
              <span className={`material-symbols-outlined text-[24px] ${v.color}`}>{v.icon}</span>
            </div>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="font-headline font-bold text-base text-on-surface group-hover:text-primary transition-colors">
                {v.name}
              </h2>
              {v.status === "coming_soon" && (
                <span className="text-[9px] font-label font-bold uppercase tracking-wider bg-surface-container-high text-on-surface-variant px-1.5 py-0.5 rounded">
                  Soon
                </span>
              )}
            </div>
            <p className="text-sm font-body text-on-surface-variant">{v.description}</p>
            <div className="mt-4 flex items-center gap-1 text-xs font-label font-semibold text-primary opacity-0 group-hover:opacity-100 transition-opacity">
              Open venture
              <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
