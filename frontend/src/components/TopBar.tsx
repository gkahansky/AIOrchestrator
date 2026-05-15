import { useState, useRef, useEffect } from "react"
import { useNavigate } from "react-router-dom"

interface TopBarProps {
  onMenuToggle: () => void
}

const VENTURES = [
  {
    id: "market-research",
    label: "Market Research",
    description: "Multi-LLM research committee — BI, legal, medical, academic",
    icon: "analytics",
    color: "text-primary",
    bg: "bg-primary/10",
    to: "/market-research",
  },
  {
    id: "marketing-audit",
    label: "Marketing Audit",
    description: "Website SEO & marketing performance audit",
    icon: "search",
    color: "text-secondary",
    bg: "bg-secondary/10",
    to: "/ventures/marketing-audit",
  },
  {
    id: "accessibility-audit",
    label: "Accessibility Audit",
    description: "Automated WCAG scan & heuristic reporting",
    icon: "accessibility_new",
    color: "text-tertiary",
    bg: "bg-tertiary/10",
    to: "/ventures/accessibility-audit",
  },
  {
    id: "security-audit",
    label: "Security Audit",
    description: "Web application penetration testing & vulnerability report",
    icon: "security",
    color: "text-error",
    bg: "bg-error/10",
    to: "/ventures/security-audit",
  },
]

export default function TopBar({ onMenuToggle }: TopBarProps) {
  const [search, setSearch] = useState("")
  const [showVentureMenu, setShowVentureMenu] = useState(false)
  const navigate = useNavigate()
  const menuRef = useRef<HTMLDivElement>(null)

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (search.trim()) {
      navigate(`/jobs?q=${encodeURIComponent(search.trim())}`)
    }
  }

  // Close on outside click
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowVentureMenu(false)
      }
    }
    if (showVentureMenu) document.addEventListener("mousedown", onClickOutside)
    return () => document.removeEventListener("mousedown", onClickOutside)
  }, [showVentureMenu])

  return (
    <header className="fixed top-0 left-0 right-0 md:left-64 h-16 bg-white/70 backdrop-blur-xl border-b border-outline-variant/15 flex items-center justify-between px-4 md:px-6 z-30 gap-3">
      {/* Hamburger — mobile only */}
      <button
        onClick={onMenuToggle}
        className="md:hidden p-2 rounded-xl hover:bg-surface-container-low transition-colors shrink-0"
        aria-label="Open menu"
      >
        <span className="material-symbols-outlined text-[22px] text-on-surface-variant">menu</span>
      </button>

      {/* Search */}
      <form onSubmit={handleSearch} className="hidden sm:flex items-center flex-1 max-w-xs">
        <div className="relative w-full">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant">
            search
          </span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search jobs…"
            className="pl-9 pr-4 py-2 text-sm font-label bg-surface-container-low rounded-xl outline-none border border-transparent focus:border-primary/30 focus:bg-surface-container-lowest w-full text-on-surface placeholder:text-on-surface-variant/60 transition-all"
          />
        </div>
      </form>

      {/* Right actions */}
      <div className="flex items-center gap-2 ml-auto">
        {/* Notification bell */}
        <button className="relative p-2 rounded-xl hover:bg-surface-container-low transition-colors">
          <span className="material-symbols-outlined text-[22px] text-on-surface-variant">
            notifications
          </span>
        </button>

        {/* New Order button + dropdown */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setShowVentureMenu(v => !v)}
            className="flex items-center gap-1.5 px-3 md:px-4 py-2 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary text-sm font-label font-semibold shadow-float hover:opacity-90 transition-opacity"
          >
            <span className="material-symbols-outlined text-[16px]">add</span>
            <span className="hidden sm:inline">New Order</span>
            <span className="material-symbols-outlined text-[14px] hidden sm:inline">
              {showVentureMenu ? "expand_less" : "expand_more"}
            </span>
          </button>

          {showVentureMenu && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.12)] border border-outline-variant/20 overflow-hidden z-50">
              <div className="px-4 pt-3 pb-2">
                <p className="text-xs font-label font-bold uppercase tracking-widest text-on-surface-variant">
                  Select a service
                </p>
              </div>
              <div className="divide-y divide-outline-variant/10">
                {VENTURES.map(v => (
                  <button
                    key={v.id}
                    onClick={() => { navigate(v.to); setShowVentureMenu(false) }}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-container-low transition-colors text-left"
                  >
                    <div className={`w-9 h-9 rounded-xl ${v.bg} flex items-center justify-center shrink-0`}>
                      <span className={`material-symbols-outlined text-[18px] ${v.color}`}>{v.icon}</span>
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-label font-semibold text-on-surface">{v.label}</p>
                      <p className="text-xs text-on-surface-variant truncate">{v.description}</p>
                    </div>
                    <span className="material-symbols-outlined text-[16px] text-on-surface-variant/40 ml-auto shrink-0">
                      arrow_forward
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Env badge */}
        <span className="hidden md:inline bg-primary text-on-primary text-[10px] font-label font-bold uppercase tracking-widest px-2 py-0.5 rounded-full">
          Prod
        </span>
      </div>
    </header>
  )
}
