import { useState } from "react"
import { useNavigate } from "react-router-dom"

interface TopBarProps {
  onMenuToggle: () => void
}

export default function TopBar({ onMenuToggle }: TopBarProps) {
  const [search, setSearch] = useState("")
  const navigate = useNavigate()

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (search.trim()) {
      navigate(`/jobs?q=${encodeURIComponent(search.trim())}`)
    }
  }

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

      {/* Search — hidden on small phones, visible from sm up */}
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

        {/* New Order button */}
        <button
          onClick={() => navigate("/market-research")}
          className="flex items-center gap-1.5 px-3 md:px-4 py-2 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary text-sm font-label font-semibold shadow-float hover:opacity-90 transition-opacity"
        >
          <span className="material-symbols-outlined text-[16px]">add</span>
          <span className="hidden sm:inline">New Order</span>
        </button>

        {/* Env badge — hidden on mobile */}
        <span className="hidden md:inline bg-primary text-on-primary text-[10px] font-label font-bold uppercase tracking-widest px-2 py-0.5 rounded-full">
          Prod
        </span>
      </div>
    </header>
  )
}
