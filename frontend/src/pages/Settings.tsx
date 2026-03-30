import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { fetchSettings, testApiKey, updateApiKey, fetchHealth } from "../api"
import type { ApiKey } from "../types"

type Tab = "api_keys" | "notifications" | "environment"

function HealthDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    healthy: "bg-emerald-500",
    degraded: "bg-amber-400",
    down: "bg-error",
  }
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[status] ?? "bg-slate-400"}`} />
}

function ApiKeysTab() {
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ["settings", "keys"],
    queryFn: () => fetchSettings("keys"),
  })

  const [editingService, setEditingService] = useState<string | null>(null)
  const [editValue, setEditValue] = useState("")
  const [testResults, setTestResults] = useState<Record<string, { status: string; message: string }>>({})

  const testMutation = useMutation({
    mutationFn: (service: string) => testApiKey(service),
    onSuccess: (result) => {
      setTestResults((prev) => ({
        ...prev,
        [result.service]: { status: result.status, message: result.message },
      }))
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ service, value }: { service: string; value: string }) =>
      updateApiKey(service, value),
    onSuccess: () => {
      setEditingService(null)
      setEditValue("")
      void qc.invalidateQueries({ queryKey: ["settings", "keys"] })
    },
  })

  if (error) {
    return (
      <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label">
        Failed to load API keys: {(error as Error).message}
      </div>
    )
  }

  const keys: ApiKey[] = data?.keys ?? []

  return (
    <div className="space-y-4">
      <p className="text-sm font-body text-on-surface-variant">
        Manage API keys for external service integrations. Keys are stored encrypted at rest.
      </p>

      <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-container-low border-b border-outline-variant/10">
              {["Service", "Key (masked)", "Last Tested", "Status", "Actions"].map((h) => (
                <th
                  key={h}
                  className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/10">
            {isLoading
              ? Array(5)
                  .fill(null)
                  .map((_, i) => (
                    <tr key={i}>
                      {Array(5)
                        .fill(null)
                        .map((__, j) => (
                          <td key={j} className="px-4 py-3">
                            <div className="h-4 bg-surface-dim rounded animate-pulse" />
                          </td>
                        ))}
                    </tr>
                  ))
              : keys.map((key) => {
                  const testResult = testResults[key.service]
                  return (
                    <tr key={key.service} className="hover:bg-surface-container-low/40 transition-colors">
                      <td className="px-4 py-3 font-label font-medium text-on-surface">
                        {key.service}
                      </td>
                      <td className="px-4 py-3">
                        {editingService === key.service ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="password"
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              placeholder="New value…"
                              className="px-3 py-1.5 text-sm font-label bg-surface-container-low rounded-lg border border-outline-variant/30 focus:border-primary/40 focus:outline-none text-on-surface w-48 transition-colors"
                            />
                            <button
                              onClick={() =>
                                updateMutation.mutate({ service: key.service, value: editValue })
                              }
                              disabled={updateMutation.isPending || !editValue}
                              className="text-xs font-label font-semibold text-primary hover:underline disabled:opacity-40"
                            >
                              {updateMutation.isPending ? "Saving…" : "Save"}
                            </button>
                            <button
                              onClick={() => {
                                setEditingService(null)
                                setEditValue("")
                              }}
                              className="text-xs font-label text-on-surface-variant hover:text-on-surface"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <span className="font-mono text-xs text-on-surface-variant">
                            {key.masked_value}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs font-label text-on-surface-variant">
                        {key.last_tested
                          ? new Date(key.last_tested).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "Never"}
                      </td>
                      <td className="px-4 py-3">
                        {testResult ? (
                          <span
                            className={`text-xs font-label font-medium ${
                              testResult.status === "ok" ? "text-emerald-600" : "text-error"
                            }`}
                          >
                            {testResult.status === "ok" ? "✓ OK" : "✗ Failed"}
                          </span>
                        ) : (
                          <span
                            className={`text-xs font-label ${
                              key.test_status === "ok"
                                ? "text-emerald-600"
                                : key.test_status === "failed"
                                ? "text-error"
                                : "text-on-surface-variant"
                            }`}
                          >
                            {key.test_status === "ok"
                              ? "✓ OK"
                              : key.test_status === "failed"
                              ? "✗ Failed"
                              : "Untested"}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => testMutation.mutate(key.service)}
                            disabled={testMutation.isPending}
                            className="text-xs font-label font-semibold text-on-surface-variant hover:text-primary transition-colors disabled:opacity-40"
                          >
                            Test
                          </button>
                          <button
                            onClick={() => {
                              setEditingService(key.service)
                              setEditValue("")
                            }}
                            className="text-xs font-label font-semibold text-primary hover:underline"
                          >
                            Edit
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
            {!isLoading && keys.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm font-label text-on-surface-variant">
                  No API keys configured
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function NotificationsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["settings", "notifications"],
    queryFn: () => fetchSettings("notifications"),
  })

  const [slack, setSlack] = useState("")
  const [emailFailure, setEmailFailure] = useState(false)
  const [emailReview, setEmailReview] = useState(false)
  const [saved, setSaved] = useState(false)

  // Sync from server data
  if (data?.notifications && !saved) {
    if (slack === "" && data.notifications.slack_webhook) setSlack(data.notifications.slack_webhook)
    if (!emailFailure && data.notifications.email_on_failure) setEmailFailure(data.notifications.email_on_failure)
    if (!emailReview && data.notifications.email_on_review) setEmailReview(data.notifications.email_on_review)
  }

  return (
    <div className="max-w-md space-y-6">
      <p className="text-sm font-body text-on-surface-variant">
        Configure alerts and notification channels.
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-xs font-label font-medium text-on-surface-variant mb-1.5 uppercase tracking-wider">
            Slack Webhook URL
          </label>
          {isLoading ? (
            <div className="h-10 bg-surface-dim rounded-xl animate-pulse" />
          ) : (
            <input
              type="text"
              value={slack}
              onChange={(e) => setSlack(e.target.value)}
              placeholder="https://hooks.slack.com/services/…"
              className="w-full px-4 py-2.5 text-sm font-label bg-surface-container-low rounded-xl border border-transparent focus:border-primary/40 focus:outline-none text-on-surface placeholder:text-on-surface-variant/50 transition-colors"
            />
          )}
        </div>

        <div className="space-y-3">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={emailFailure}
              onChange={(e) => setEmailFailure(e.target.checked)}
              className="w-4 h-4 accent-primary"
            />
            <div>
              <p className="text-sm font-label font-medium text-on-surface">Email on job failure</p>
              <p className="text-xs font-label text-on-surface-variant">
                Send alert when a pipeline job fails
              </p>
            </div>
          </label>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={emailReview}
              onChange={(e) => setEmailReview(e.target.checked)}
              className="w-4 h-4 accent-primary"
            />
            <div>
              <p className="text-sm font-label font-medium text-on-surface">Email on review needed</p>
              <p className="text-xs font-label text-on-surface-variant">
                Send alert when a job requires manual review
              </p>
            </div>
          </label>
        </div>

        <button
          onClick={() => setSaved(true)}
          className="px-5 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-label font-semibold hover:opacity-90 transition-opacity"
        >
          Save Preferences
        </button>

        {saved && (
          <p className="text-xs font-label text-emerald-600 flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">check_circle</span>
            Saved (demo — backend integration required)
          </p>
        )}
      </div>
    </div>
  )
}

function EnvironmentTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-error-container text-on-error-container rounded-xl px-4 py-3 text-sm font-label">
          Failed to load health data: {(error as Error).message}
        </div>
      )}

      {/* Overview */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
          <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">
            Overall Status
          </p>
          {isLoading ? (
            <div className="h-5 w-16 bg-surface-dim rounded animate-pulse" />
          ) : (
            <div className="flex items-center gap-2">
              <HealthDot status={data?.status ?? "down"} />
              <span className="text-sm font-label font-semibold text-on-surface capitalize">
                {data?.status ?? "—"}
              </span>
            </div>
          )}
        </div>
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
          <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">
            Environment
          </p>
          {isLoading ? (
            <div className="h-5 w-20 bg-surface-dim rounded animate-pulse" />
          ) : (
            <span className="text-sm font-label font-semibold text-on-surface capitalize">
              {data?.environment ?? "—"}
            </span>
          )}
        </div>
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-float">
          <p className="text-[11px] font-label font-medium uppercase tracking-widest text-on-surface-variant mb-1">
            Version
          </p>
          {isLoading ? (
            <div className="h-5 w-16 bg-surface-dim rounded animate-pulse" />
          ) : (
            <span className="text-sm font-label font-mono text-on-surface">{data?.version ?? "—"}</span>
          )}
        </div>
      </div>

      {/* Services table */}
      <div className="bg-surface-container-lowest rounded-xl shadow-float overflow-hidden">
        <div className="px-5 py-4 border-b border-outline-variant/15">
          <h2 className="font-headline font-bold text-sm text-on-surface">Service Health</h2>
          {data?.checked_at && (
            <p className="text-xs font-label text-on-surface-variant mt-0.5">
              Last checked:{" "}
              {new Date(data.checked_at).toLocaleString("en-US", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </p>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-container-low border-b border-outline-variant/10">
                {["Service", "Status", "Latency", "Message"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-2.5 text-left text-[11px] font-label font-semibold uppercase tracking-wider text-on-surface-variant"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/10">
              {isLoading
                ? Array(5)
                    .fill(null)
                    .map((_, i) => (
                      <tr key={i}>
                        {Array(4)
                          .fill(null)
                          .map((__, j) => (
                            <td key={j} className="px-4 py-3">
                              <div className="h-4 bg-surface-dim rounded animate-pulse" />
                            </td>
                          ))}
                      </tr>
                    ))
                : data?.services.map((svc) => (
                    <tr key={svc.name} className="hover:bg-surface-container-low/40 transition-colors">
                      <td className="px-4 py-3 font-label font-medium text-on-surface">{svc.name}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <HealthDot status={svc.status} />
                          <span className="text-sm font-label text-on-surface capitalize">
                            {svc.status}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm font-label text-on-surface-variant">
                        {svc.latency_ms != null ? `${svc.latency_ms}ms` : "—"}
                      </td>
                      <td className="px-4 py-3 text-sm font-label text-on-surface-variant">
                        {svc.message ?? "—"}
                      </td>
                    </tr>
                  ))}
              {!isLoading && !data?.services.length && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-sm font-label text-on-surface-variant">
                    No service data
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default function Settings() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get("tab") as Tab | null
  const [activeTab, setActiveTab] = useState<Tab>(tabParam === "environment" ? "environment" : "api_keys")

  function switchTab(t: Tab) {
    setActiveTab(t)
    setSearchParams({ tab: t })
  }

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: "api_keys", label: "API Keys", icon: "key" },
    { id: "notifications", label: "Notifications", icon: "notifications" },
    { id: "environment", label: "Environment", icon: "monitor_heart" },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-headline font-bold text-2xl text-on-surface">Settings</h1>
        <p className="text-sm font-body text-on-surface-variant mt-0.5">
          Platform configuration and integrations
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-0.5 bg-surface-container-low p-1 rounded-xl w-fit">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => switchTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-label font-medium transition-colors ${
              activeTab === t.id
                ? "bg-surface-container-lowest text-on-surface shadow-float"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === "api_keys" && <ApiKeysTab />}
      {activeTab === "notifications" && <NotificationsTab />}
      {activeTab === "environment" && <EnvironmentTab />}
    </div>
  )
}
