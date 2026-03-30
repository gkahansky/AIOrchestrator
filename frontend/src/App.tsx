import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import Layout from "./components/Layout"
import Login from "./pages/Login"
import Dashboard from "./pages/Dashboard"
import JobDetail from "./pages/JobDetail"
import Ventures from "./pages/Ventures"
import MarketingAudit from "./pages/ventures/MarketingAudit"
import ContentStudio from "./pages/ventures/ContentStudio"
import EtsyVenture from "./pages/ventures/EtsyVenture"
import Finance from "./pages/Finance"
import Settings from "./pages/Settings"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 2,
    },
  },
})

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("api_token")
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="jobs/:id" element={<JobDetail />} />
            <Route path="ventures" element={<Ventures />} />
            <Route path="ventures/marketing-audit" element={<MarketingAudit />} />
            <Route path="ventures/content-studio" element={<ContentStudio />} />
            <Route path="ventures/etsy" element={<EtsyVenture />} />
            <Route path="finance" element={<Finance />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
