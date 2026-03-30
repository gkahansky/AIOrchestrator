import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"

const BASE = import.meta.env.VITE_API_URL || "https://api.echoforge.biz"

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: object) => void
          renderButton: (el: HTMLElement, config: object) => void
          prompt: () => void
        }
      }
    }
  }
}

export default function Login() {
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [clientId, setClientId] = useState<string | null>(null)
  const navigate = useNavigate()

  // Fetch public auth config from API (gets the Google Client ID)
  useEffect(() => {
    fetch(`${BASE}/api/auth/config`)
      .then((r) => r.json())
      .then((data) => {
        if (!data.auth_enabled) {
          // Dev mode — skip Google login
          localStorage.setItem("api_token", "dev-mode")
          navigate("/")
          return
        }
        setClientId(data.google_client_id)
      })
      .catch(() => {
        // If config fails, fall through to show the button with env var fallback
        setClientId(import.meta.env.VITE_GOOGLE_CLIENT_ID || "")
      })
  }, [navigate])

  // Once we have the client ID, load and init the Google Identity Services script
  useEffect(() => {
    if (!clientId) return

    const scriptId = "gsi-script"
    if (document.getElementById(scriptId)) {
      initGoogle()
      return
    }

    const script = document.createElement("script")
    script.id = scriptId
    script.src = "https://accounts.google.com/gsi/client"
    script.async = true
    script.defer = true
    script.onload = initGoogle
    document.head.appendChild(script)
  }, [clientId])

  function initGoogle() {
    if (!window.google || !clientId) return
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: handleGoogleCredential,
    })
    const btn = document.getElementById("google-signin-btn")
    if (btn) {
      window.google.accounts.id.renderButton(btn, {
        type: "standard",
        shape: "rectangular",
        theme: "outline",
        text: "signin_with",
        size: "large",
        logo_alignment: "left",
        width: 320,
      })
    }
  }

  async function handleGoogleCredential(response: { credential: string }) {
    setLoading(true)
    setError("")
    try {
      const res = await fetch(`${BASE}/api/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential: response.credential }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || "Sign-in failed. Make sure you're using the authorised account.")
        return
      }
      const data = await res.json()
      localStorage.setItem("api_token", data.token)
      navigate("/")
    } catch {
      setError("Could not reach the platform API. Check your connection and try again.")
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
        <div className="bg-surface-container-lowest rounded-xl p-8" style={{ boxShadow: "0px 20px 40px rgba(19,27,46,0.06)" }}>
          <h1 className="font-headline font-bold text-lg text-on-surface mb-1">Sign in</h1>
          <p className="text-sm font-body text-on-surface-variant mb-8">
            Use your Google account to access the platform.
          </p>

          {loading ? (
            <div className="flex items-center justify-center gap-3 py-4">
              <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-on-surface-variant font-label">Signing in…</span>
            </div>
          ) : (
            <div className="flex justify-center">
              {/* Google renders its own button here */}
              <div id="google-signin-btn" />
            </div>
          )}

          {error && (
            <p className="mt-4 text-xs font-label text-error bg-error-container px-3 py-2 rounded-sm">
              {error}
            </p>
          )}
        </div>

        <p className="text-center text-xs text-on-surface-variant mt-6 font-label">
          EchoForge &middot; AI-Infra Platform v0.1
        </p>
      </div>
    </div>
  )
}
