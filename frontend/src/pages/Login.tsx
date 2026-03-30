import { useState } from "react"
import { useNavigate } from "react-router-dom"

export default function Login() {
  const [token, setToken] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!token.trim()) {
      setError("Please enter an API token.")
      return
    }
    setLoading(true)
    setError("")

    try {
      const base = import.meta.env.VITE_API_URL || "https://api.echoforge.biz"
      const res = await fetch(`${base}/api/health`, {
        headers: {
          Authorization: `Bearer ${token.trim()}`,
          "Content-Type": "application/json",
        },
      })

      if (res.ok || res.status === 200) {
        localStorage.setItem("api_token", token.trim())
        navigate("/")
      } else if (res.status === 401 || res.status === 403) {
        setError("Invalid token. Please check and try again.")
      } else {
        // Accept token even if API returns unexpected status — might be offline
        localStorage.setItem("api_token", token.trim())
        navigate("/")
      }
    } catch {
      // Network error — store token anyway (API might be temporarily down)
      localStorage.setItem("api_token", token.trim())
      navigate("/")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="font-headline font-black text-3xl text-on-surface mb-1">AI-Infra</div>
          <div className="text-xs font-label font-medium uppercase tracking-[0.18em] text-on-surface-variant">
            Infrastructure Admin
          </div>
        </div>

        {/* Card */}
        <div className="bg-surface-container-lowest rounded-2xl p-8 shadow-float">
          <h1 className="font-headline font-bold text-lg text-on-surface mb-1">Sign in</h1>
          <p className="text-sm font-body text-on-surface-variant mb-6">
            Enter your platform API token to continue.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
                API Token
              </label>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="sk-…"
                autoComplete="current-password"
                className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
              />
            </div>

            {error && (
              <p className="text-xs font-label text-error bg-error-container px-3 py-2 rounded-lg">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary text-sm font-label font-semibold shadow-float hover:opacity-90 transition-opacity disabled:opacity-60"
            >
              {loading ? "Verifying…" : "Continue"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-on-surface-variant mt-6 font-label">
          EchoForge &middot; AI-Infra Platform v0.1
        </p>
      </div>
    </div>
  )
}
