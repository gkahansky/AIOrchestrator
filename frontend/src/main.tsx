import React from "react"
import ReactDOM from "react-dom/client"
import App from "./App"
import "./index.css"

// Global 401 interceptor — redirects to /login when any API call returns Unauthorized.
// This catches expired JWT sessions without needing per-page error handling.
;(function installAuthInterceptor() {
  const _fetch = window.fetch.bind(window)
  window.fetch = async (...args) => {
    const response = await _fetch(...args)
    if (response.status === 401) {
      const url = typeof args[0] === "string" ? args[0] : (args[0] as Request).url
      // Skip the auth endpoints themselves (login, config) to avoid redirect loops.
      if (!url.includes("/api/auth/")) {
        localStorage.removeItem("api_token")
        window.location.replace("/login?reason=session_expired")
      }
    }
    return response
  }
})()

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
