import { useState } from "react"
import { useNavigate } from "react-router-dom"

export default function TopBar() {
  const [search, setSearch] = useState("")
  const navigate = useNavigate()

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (search.trim()) {
      navigate(`/jobs?q=${encodeURIComponent(search.trim())}`)
    }
  }

  return (
    <header className="fixed top-0 right-0 w-[calc(100%-16rem)] h-16 bg-white/70 backdrop-blur-xl border-b border-outline-variant/15 flex items-center justify-between px-6 z-30">
      {/* Search */}
      <form onSubmit={handleSearch} className="flex items-center">
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant">
            search
          </span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search jobs, orders…"
            className="pl-9 pr-4 py-2 text-sm font-label bg-surface-container-low rounded-xl outline-none border border-transparent focus:border-primary/30 focus:bg-surface-container-lowest w-64 text-on-surface placeholder:text-on-surface-variant/60 transition-all"
          />
        </div>
      </form>

      {/* Right actions */}
      <div className="flex items-center gap-3">
        {/* Notification bell */}
        <button className="relative p-2 rounded-xl hover:bg-surface-container-low transition-colors">
          <span className="material-symbols-outlined text-[22px] text-on-surface-variant">
            notifications
          </span>
        </button>

        {/* New Order button */}
        <button
          onClick={() => navigate("/ventures")}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary text-sm font-label font-semibold shadow-float hover:opacity-90 transition-opacity"
        >
          <span className="material-symbols-outlined text-[16px]">add</span>
          New Order
        </button>

        {/* Env badge */}
        <span className="bg-primary text-on-primary text-[10px] font-label font-bold uppercase tracking-widest px-2 py-0.5 rounded-full">
          Prod
        </span>
      </div>
    </header>
  )
}
