import { Outlet } from "react-router-dom"
import Sidebar from "./Sidebar"
import TopBar from "./TopBar"

export default function Layout() {
  return (
    <div className="min-h-screen bg-background text-on-background">
      <Sidebar />
      <TopBar />
      <main className="ml-64 pt-16 min-h-screen">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
