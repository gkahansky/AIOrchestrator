import { useState } from "react"
import { Outlet } from "react-router-dom"
import Sidebar from "./Sidebar"
import TopBar from "./TopBar"

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen bg-background text-on-background">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Mobile overlay — dims content when sidebar is open */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <TopBar onMenuToggle={() => setSidebarOpen((o) => !o)} />

      <main className="md:ml-64 pt-16 min-h-screen">
        <div className="p-4 md:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
