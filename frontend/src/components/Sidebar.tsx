import { NavLink, useNavigate } from "react-router-dom"

interface NavItem {
  label: string
  to: string
  icon: string
}

const navItems: NavItem[] = [
  { label: "Dashboard", to: "/", icon: "dashboard" },
  { label: "Ventures", to: "/ventures", icon: "account_tree" },
  { label: "Gig Generator", to: "/gigs", icon: "storefront" },
  { label: "Strategy Room", to: "/strategy-room", icon: "psychology" },
  { label: "Market Research", to: "/market-research", icon: "analytics" },
  { label: "To Do List", to: "/roadmap", icon: "checklist" },
  { label: "Marketing", to: "/marketing", icon: "campaign" },
  { label: "Campaigns", to: "/campaigns", icon: "flag" },
  { label: "Finance", to: "/finance", icon: "payments" },
  { label: "Settings", to: "/settings", icon: "settings" },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const navigate = useNavigate()

  function handleLogout() {
    localStorage.removeItem("api_token")
    navigate("/login")
  }

  return (
    <aside
      className={[
        "fixed top-0 left-0 h-screen w-64 bg-surface-container-lowest border-r border-outline-variant/15 flex flex-col z-40",
        "transition-transform duration-200",
        open ? "translate-x-0" : "-translate-x-full md:translate-x-0",
      ].join(" ")}
    >
      {/* Logo */}
      <div className="px-6 pt-7 pb-6 flex items-center justify-between">
        <div>
          <div className="font-headline font-black text-xl text-on-surface tracking-tight">
            Plan B
          </div>
          <div className="text-[10px] font-label font-medium uppercase tracking-[0.15em] text-on-surface-variant mt-0.5">
            Infrastructure Admin
          </div>
        </div>
        {/* Close button — mobile only */}
        <button
          onClick={onClose}
          className="md:hidden p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-low transition-colors"
          aria-label="Close menu"
        >
          <span className="material-symbols-outlined text-[22px]">close</span>
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 space-y-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            onClick={onClose}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-label font-medium transition-colors",
                isActive
                  ? "text-primary font-semibold border-r-4 border-primary bg-primary-fixed/30"
                  : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
              ].join(" ")
            }
          >
            <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Bottom */}
      <div className="px-5 pb-6 space-y-2">
        <div className="flex items-center gap-2 mb-1">
          <span className="bg-primary text-on-primary text-[10px] font-label font-bold uppercase tracking-widest px-2 py-0.5 rounded-sm">
            Production
          </span>
        </div>
        <NavLink
          to="/settings?tab=environment"
          onClick={onClose}
          className="flex items-center gap-2 text-xs font-label text-on-surface-variant hover:text-primary transition-colors py-1"
        >
          <span className="material-symbols-outlined text-[16px]">monitor_heart</span>
          System Health
        </NavLink>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-xs font-label text-on-surface-variant hover:text-error transition-colors py-1 w-full text-left"
        >
          <span className="material-symbols-outlined text-[16px]">logout</span>
          Sign out
        </button>
      </div>
    </aside>
  )
}
