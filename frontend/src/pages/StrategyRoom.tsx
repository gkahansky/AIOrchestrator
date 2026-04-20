import { useState, useRef, useCallback, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  fetchProposals, fetchAdvisorRuns, fetchAdvisorDiagnostics,
  approveProposal, rejectProposal,
  fetchAdvisors, updateAdvisorPrompt,
  fetchRoadmap, fetchRoadmapDone, fetchRoadmapFeatures,
  createRoadmapFeature, createRoadmapItem, updateRoadmapItem,
  deleteRoadmapItem, reorderRoadmapItems,
  triggerAdvisor, chatWithAdvisors,
  fetchAvailableLlms, createMarketResearchSession, uploadResearchDocs,
  fetchMarketResearchSessions, fetchMarketResearchSession, rerunResearchSession,
  retryResearchSession,
} from "../api"
import type { MarketResearchDetail } from "../api"
import type {
  AdvisorConfig,
  AdvisoryProposal,
  RoadmapItem,
  RoadmapFeature,
  RoadmapItemType,
  RoadmapStatus,
  ChatMessage,
  ChatSession,
} from "../types"

// ─────────────────────────────────────────────────────────────────────────────
// Static agent config — names, colours, icons, skills per agent
// ─────────────────────────────────────────────────────────────────────────────

interface SkillDef { name: string; todo?: boolean }

interface AgentMeta {
  displayName: string
  badge: string
  badgeClass: string
  icon: string
  borderColor: string
  iconBg: string
  iconColor: string
  proposalClass: string
  description: string
  schedule: string
  skills: SkillDef[]
}

const AGENT_META: Record<string, AgentMeta> = {
  architect: {
    displayName: "System Architect",
    badge: "Technical",
    badgeClass: "bg-blue-100 text-blue-800",
    icon: "architecture",
    borderColor: "border-l-[#003d9b]",
    iconBg: "bg-[#dae2ff]",
    iconColor: "text-[#003d9b]",
    proposalClass: "bg-blue-50 border-blue-200 text-blue-700 hover:bg-blue-100",
    description: "Reviews PRs for code quality, flags technical debt and security flaws, and proposes architectural improvements.",
    schedule: "Triggered on every GitHub PR opened or synchronized",
    skills: [
      { name: "PR Code Review" },
      { name: "Tech Debt Scan" },
      { name: "Dependency Scan", todo: true },
      { name: "Inline PR Comments", todo: true },
    ],
  },
  marketing: {
    displayName: "Marketing & Sales",
    badge: "Marketing",
    badgeClass: "bg-orange-100 text-orange-800",
    icon: "campaign",
    borderColor: "border-l-[#a33500]",
    iconBg: "bg-[#ffdbcf]",
    iconColor: "text-[#a33500]",
    proposalClass: "bg-orange-50 border-orange-200 text-orange-700 hover:bg-orange-100",
    description: "Monitors listings and revenue, evaluates pricing, and recommends promotional audits and new gig features.",
    schedule: "Manual trigger (TODO: auto on revenue drop)",
    skills: [
      { name: "Revenue Analysis" },
      { name: "Pricing Optimization" },
      { name: "Inventory Monitor" },
      { name: "Competitor Pricing", todo: true },
    ],
  },
  product: {
    displayName: "Product Lead",
    badge: "Execution",
    badgeClass: "bg-slate-100 text-slate-700",
    icon: "inventory_2",
    borderColor: "border-l-[#525f73]",
    iconBg: "bg-[#d6e3fb]",
    iconColor: "text-[#525f73]",
    proposalClass: "bg-slate-100 border-slate-200 text-slate-700 hover:bg-slate-200",
    description: "Analyses pipeline bottlenecks, measures Human-in-the-Loop efficiency, and surfaces automation opportunities.",
    schedule: "After every completed pipeline job (Celery task_success)",
    skills: [
      { name: "Pipeline Analysis" },
      { name: "Bottleneck Detection" },
      { name: "Automation Suggestions" },
      { name: "Backlog Scoring", todo: true },
    ],
  },
  executive: {
    displayName: "The Executive",
    badge: "Governance",
    badgeClass: "bg-gray-200 text-gray-700",
    icon: "account_balance",
    borderColor: "border-l-[#434654]",
    iconBg: "bg-[#e7e8e9]",
    iconColor: "text-[#191c1d]",
    proposalClass: "bg-gray-100 border-gray-200 text-gray-700 hover:bg-gray-200",
    description: "Consumes the weekly financial digest, assesses portfolio health, and sets sprint focus for all ventures.",
    schedule: "Weekly — Monday 08:00 UTC (Celery Beat)",
    skills: [
      { name: "Weekly Business Overview" },
      { name: "Executive Summary" },
      { name: "Margin Monitoring", todo: true },
      { name: "Action Plan Synthesis", todo: true },
    ],
  },
}

const AGENT_ORDER = ["architect", "marketing", "product", "executive"]

// ─────────────────────────────────────────────────────────────────────────────
// Roadmap helpers (unchanged logic, new styling)
// ─────────────────────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  in_testing: "In testing",
  ready_for_deployment: "Ready for deployment",
  done: "Done",
}

const STATUS_COLOURS: Record<string, string> = {
  not_started: "bg-gray-100 text-gray-600",
  in_progress: "bg-blue-100 text-blue-700",
  in_testing: "bg-yellow-100 text-yellow-700",
  ready_for_deployment: "bg-green-100 text-green-700",
  done: "bg-emerald-100 text-emerald-700",
}

const TYPE_COLOURS: Record<string, string> = {
  "New feature": "bg-purple-100 text-purple-700",
  "Bug": "bg-red-100 text-red-700",
  "Feature enhancement": "bg-orange-100 text-orange-700",
}

const WIP_STATUSES: RoadmapStatus[] = ["in_progress", "in_testing", "ready_for_deployment"]
const ALL_STATUSES: RoadmapStatus[] = ["not_started", ...WIP_STATUSES, "done"]
const ITEM_TYPES: RoadmapItemType[] = ["New feature", "Bug", "Feature enhancement"]

// ─────────────────────────────────────────────────────────────────────────────
// Agent Prompt Editor Modal
// ─────────────────────────────────────────────────────────────────────────────

function AgentPromptEditor({
  advisor,
  onClose,
}: {
  advisor: AdvisorConfig
  onClose: () => void
}) {
  const meta = AGENT_META[advisor.id]
  const [text, setText] = useState(advisor.system_prompt)
  const queryClient = useQueryClient()

  const saveMutation = useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) =>
      updateAdvisorPrompt(id, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategy_advisors"] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-slate-950 w-full max-w-5xl rounded-2xl overflow-hidden shadow-2xl border border-white/10 flex flex-col max-h-[90vh]">
        {/* Editor header */}
        <div className="flex items-center justify-between px-6 py-4 bg-slate-900 border-b border-white/5 shrink-0">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <div className="w-3 h-3 rounded-full bg-yellow-500" />
              <div className="w-3 h-3 rounded-full bg-green-500" />
            </div>
            <span className="text-xs font-mono text-slate-400 ml-2">
              {advisor.prompt_ref}.md
              <span className="ml-3 text-slate-600">·</span>
              <span className="ml-3 text-slate-500">{meta?.displayName ?? advisor.id}</span>
            </span>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        {/* Textarea */}
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          className="flex-1 bg-slate-950 text-slate-200 font-mono text-base leading-relaxed p-8 resize-none focus:outline-none min-h-0 overflow-y-auto"
          spellCheck={false}
        />

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-900 border-t border-white/5 flex justify-end gap-3 shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors"
          >
            Discard
          </button>
          <button
            onClick={() => saveMutation.mutate({ id: advisor.id, content: text })}
            disabled={saveMutation.isPending}
            className="px-6 py-2 rounded-lg text-sm font-bold text-white transition-all shadow-lg disabled:opacity-50"
            style={{ background: "linear-gradient(135deg, #003d9b 0%, #0052cc 100%)" }}
          >
            {saveMutation.isPending ? "Saving…" : "Commit Prompt"}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Proposals Dialog — per-agent
// ─────────────────────────────────────────────────────────────────────────────

function proposalContentText(content: string | Record<string, unknown>): string {
  if (typeof content === "string") return content
  if (content && typeof content === "object") {
    const c = content as Record<string, unknown>
    return [c.summary, c.recommendation].filter(Boolean).join("\n\n") || JSON.stringify(content, null, 2)
  }
  return String(content)
}

function ProposalsDialog({
  advisorId,
  proposals,
  onClose,
}: {
  advisorId: string
  proposals: AdvisoryProposal[]
  onClose: () => void
}) {
  const meta = AGENT_META[advisorId]
  const queryClient = useQueryClient()

  const approveMutation = useMutation({
    mutationFn: approveProposal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategy_proposals"] })
      queryClient.invalidateQueries({ queryKey: ["roadmap"] })
    },
  })
  const rejectMutation = useMutation({
    mutationFn: rejectProposal,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["strategy_proposals"] }),
  })

  const filtered = proposals.filter(p => p.advisor_id === advisorId)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-surface-container-lowest w-full max-w-2xl rounded-2xl shadow-float overflow-hidden max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-5 flex items-center justify-between border-b border-surface-container shrink-0">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${meta?.iconBg}`}>
              <span className={`material-symbols-outlined text-lg ${meta?.iconColor}`}
                style={{ fontVariationSettings: "'FILL' 1" }}>
                {meta?.icon ?? "smart_toy"}
              </span>
            </div>
            <div>
              <h2 className="text-base font-bold font-headline text-on-surface">
                {meta?.displayName ?? advisorId} — Pending Proposals
              </h2>
              <p className="text-xs text-on-surface-variant">{filtered.length} proposal{filtered.length !== 1 ? "s" : ""} awaiting review</p>
            </div>
          </div>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface transition-colors p-1">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto flex-1 p-6 space-y-4">
          {filtered.length === 0 ? (
            <div className="text-center py-12">
              <span className="material-symbols-outlined text-4xl text-outline mb-3 block">
                check_circle
              </span>
              <p className="text-on-surface-variant text-sm">No pending proposals. All caught up.</p>
            </div>
          ) : (
            filtered.map(p => (
              <div key={p.id} className="bg-surface-container-low rounded-xl p-5">
                <div className="flex items-start justify-between mb-3 gap-3">
                  <div>
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 block mb-1">
                      {p.category}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-surface-container font-medium text-on-surface-variant">
                        Priority {p.priority}
                      </span>
                      <span className="text-xs text-on-surface-variant">
                        {new Date(p.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
                <p className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap">
                  {proposalContentText(p.content)}
                </p>
                <div className="flex justify-end gap-2 mt-4 pt-4 border-t border-surface-container">
                  <button
                    onClick={() => rejectMutation.mutate(p.id)}
                    disabled={rejectMutation.isPending || approveMutation.isPending}
                    className="px-4 py-2 text-sm font-medium rounded-lg border border-outline-variant/40 text-error hover:bg-error-container transition-all disabled:opacity-40"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => approveMutation.mutate(p.id)}
                    disabled={rejectMutation.isPending || approveMutation.isPending}
                    className="px-4 py-2 text-sm font-bold rounded-lg text-white transition-all shadow-sm disabled:opacity-40 hover:brightness-110"
                    style={{ background: "linear-gradient(135deg, #003d9b 0%, #0052cc 100%)" }}
                  >
                    Add to Roadmap
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Agent Settings Dialog
// ─────────────────────────────────────────────────────────────────────────────

function AgentSettingsDialog({
  advisor,
  onClose,
  onEditPrompt,
}: {
  advisor: AdvisorConfig
  onClose: () => void
  onEditPrompt: () => void
}) {
  const meta = AGENT_META[advisor.id]
  const [triggering, setTriggering] = useState(false)
  const [triggerMsg, setTriggerMsg] = useState("")

  async function handleTrigger() {
    setTriggering(true)
    try {
      await triggerAdvisor(advisor.id)
      setTriggerMsg("Queued successfully. Check back in a moment.")
    } catch (e: unknown) {
      setTriggerMsg(`Error: ${e instanceof Error ? e.message : "Unknown error"}`)
    } finally {
      setTriggering(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-surface-container-lowest w-full max-w-lg rounded-2xl shadow-float overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 flex items-center justify-between border-b border-surface-container">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${meta?.iconBg}`}>
              <span className={`material-symbols-outlined ${meta?.iconColor}`}
                style={{ fontVariationSettings: "'FILL' 1" }}>
                {meta?.icon ?? "smart_toy"}
              </span>
            </div>
            <h2 className="text-base font-bold font-headline text-on-surface">
              {meta?.displayName ?? advisor.id} — Settings
            </h2>
          </div>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface transition-colors p-1">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Model */}
          <div>
            <p className="text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 mb-2">LLM Model</p>
            <div className="flex items-center gap-2 px-4 py-3 bg-surface-container-low rounded-xl">
              <span className="material-symbols-outlined text-sm text-on-surface-variant">smart_toy</span>
              <span className="text-sm font-medium text-on-surface font-mono">{advisor.model}</span>
              <span className="ml-auto text-xs text-on-surface-variant opacity-60">Read-only</span>
            </div>
          </div>

          {/* Schedule */}
          <div>
            <p className="text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 mb-2">Task Schedule</p>
            <div className="flex items-start gap-2 px-4 py-3 bg-surface-container-low rounded-xl">
              <span className="material-symbols-outlined text-sm text-on-surface-variant mt-0.5">schedule</span>
              <span className="text-sm text-on-surface leading-relaxed">{meta?.schedule ?? "—"}</span>
            </div>
          </div>

          {/* Manual trigger */}
          <div>
            <p className="text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 mb-2">Manual Trigger</p>
            <button
              onClick={handleTrigger}
              disabled={triggering}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 border border-outline-variant/40 rounded-xl text-sm font-medium text-on-surface hover:bg-surface-container transition-all disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-sm">play_arrow</span>
              {triggering ? "Dispatching…" : "Run Now"}
            </button>
            {triggerMsg && (
              <p className="text-xs text-on-surface-variant mt-2 px-1">{triggerMsg}</p>
            )}
          </div>

          {/* System Prompt */}
          <div>
            <p className="text-[11px] font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 mb-2">System Prompt</p>
            <button
              onClick={() => { onClose(); onEditPrompt() }}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-bold text-white transition-all shadow-sm hover:brightness-110"
              style={{ background: "linear-gradient(135deg, #003d9b 0%, #0052cc 100%)" }}
            >
              <span className="material-symbols-outlined text-sm">terminal</span>
              Edit Agent Prompt
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Agent Card
// ─────────────────────────────────────────────────────────────────────────────

function AgentCard({
  advisor,
  proposals,
  selected,
  runningSkill,
  onToggleSelect,
  onPrompt,
  onProposals,
  onSettings,
  onTriggerSkill,
}: {
  advisor: AdvisorConfig
  proposals: AdvisoryProposal[]
  selected: boolean
  runningSkill: string | null
  onToggleSelect: () => void
  onPrompt: () => void
  onProposals: () => void
  onSettings: () => void
  onTriggerSkill: (skill: SkillDef) => void
}) {
  const meta = AGENT_META[advisor.id]
  const count = proposals.filter(p => p.advisor_id === advisor.id).length

  return (
    <div className={`bg-surface-container-lowest rounded-2xl p-7 border-l-4 shadow-card hover:shadow-float transition-all relative ${meta.borderColor}`}>
      {/* Checkbox + settings */}
      <div className="absolute top-5 right-5 flex items-center gap-2">
        <button
          onClick={onSettings}
          className="w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container-low transition-colors"
          title="Agent settings"
        >
          <span className="material-symbols-outlined text-sm">tune</span>
        </button>
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggleSelect}
          className="w-5 h-5 rounded border-outline-variant accent-primary cursor-pointer"
          title="Select for consultation"
        />
      </div>

      {/* Header */}
      <div className="flex items-start gap-5 mb-7">
        <div className={`w-14 h-14 rounded-2xl flex items-center justify-center shrink-0 ${meta.iconBg}`}>
          <span
            className={`material-symbols-outlined text-4xl ${meta.iconColor}`}
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            {meta.icon}
          </span>
        </div>
        <div className="pr-16">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h4 className="text-xl font-bold font-headline text-on-surface">{meta.displayName}</h4>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${meta.badgeClass}`}>
              {meta.badge}
            </span>
          </div>
          <p className="text-sm text-on-surface-variant leading-relaxed">{meta.description}</p>
        </div>
      </div>

      {/* Skills */}
      <div className="mb-6">
        <h5 className="text-[11px] font-bold text-on-surface-variant uppercase tracking-widest mb-3 font-label opacity-60">
          Skills &amp; Capabilities
        </h5>
        <div className="grid grid-cols-2 gap-2">
          {meta.skills.map(skill => {
            const skillKey = `${advisor.id}:${skill.name}`
            const isRunning = runningSkill === skillKey
            return (
              <button
                key={skill.name}
                onClick={() => onTriggerSkill(skill)}
                className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition-all text-left group/skill ${
                  skill.todo
                    ? "bg-surface-container text-on-surface-variant opacity-60 cursor-default"
                    : isRunning
                    ? "bg-primary/10 text-primary cursor-wait"
                    : "bg-surface-container-low hover:bg-surface-container-high text-on-surface"
                }`}
                disabled={skill.todo || isRunning}
                title={skill.todo ? "Coming soon" : isRunning ? "Running…" : `Run ${skill.name}`}
              >
                <span className="truncate">{skill.name}</span>
                {skill.todo ? (
                  <span className="text-[9px] font-bold text-on-surface-variant uppercase tracking-wide opacity-50 ml-1 shrink-0">TODO</span>
                ) : isRunning ? (
                  <svg className="w-3 h-3 animate-spin text-primary shrink-0 ml-1" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                ) : (
                  <span className="material-symbols-outlined text-xs opacity-0 group-hover/skill:opacity-100 transition-opacity text-primary shrink-0">bolt</span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="pt-5 border-t border-surface-container flex items-center justify-between gap-3">
        <button
          onClick={onPrompt}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold text-white transition-all shadow-sm hover:brightness-110 active:scale-95"
          style={{ background: "linear-gradient(135deg, #003d9b 0%, #0052cc 100%)" }}
        >
          <span className="material-symbols-outlined text-sm">terminal</span>
          Agent Prompt
        </button>

        <button
          onClick={onProposals}
          className={`flex items-center gap-1.5 px-3 py-1.5 border rounded-full text-xs font-bold shadow-sm transition-colors ${meta.proposalClass}`}
        >
          <span className="material-symbols-outlined text-sm">assignment_late</span>
          <span>{count} Proposal{count !== 1 ? "s" : ""}</span>
        </button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat Panel — bottom drawer with session tabs
// ─────────────────────────────────────────────────────────────────────────────

const MAX_CHAT_SESSIONS = 5

function ChatPanel({
  sessions,
  activeId,
  onSelectSession,
  onCloseSession,
  onSendMessage,
  onClose,
}: {
  sessions: ChatSession[]
  activeId: string | null
  onSelectSession: (id: string) => void
  onCloseSession: (id: string) => void
  onSendMessage: (sessionId: string, text: string) => void
  onClose: () => void
}) {
  const [input, setInput] = useState("")
  const bottomRef = useRef<HTMLDivElement>(null)
  const activeSession = sessions.find(s => s.id === activeId)

  function send() {
    if (!input.trim() || !activeId) return
    onSendMessage(activeId, input.trim())
    setInput("")
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 100)
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="mt-auto bg-surface-container-lowest w-full shadow-float rounded-t-2xl flex flex-col"
        style={{ height: "clamp(480px, 65vh, 720px)" }}
        onClick={e => e.stopPropagation()}
      >
        {/* Drag pill */}
        <div className="flex justify-center pt-3 shrink-0">
          <div className="w-10 h-1 rounded-full bg-outline-variant" />
        </div>

        {/* Session tabs + close */}
        <div className="flex items-center gap-1 px-4 pt-2 pb-0 border-b border-surface-container overflow-x-auto shrink-0">
          {sessions.map(s => (
            <div key={s.id} className="flex items-center gap-1 shrink-0">
              <button
                onClick={() => onSelectSession(s.id)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-t-lg text-xs font-medium transition-all whitespace-nowrap ${
                  s.id === activeId
                    ? "bg-surface-container text-primary border-b-2 border-primary"
                    : "text-on-surface-variant hover:text-on-surface"
                }`}
              >
                {s.loading && (
                  <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                )}
                {s.name}
              </button>
              <button
                onClick={() => onCloseSession(s.id)}
                className="text-on-surface-variant hover:text-error transition-colors p-0.5"
              >
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            </div>
          ))}
          <button
            onClick={onClose}
            className="ml-auto flex items-center gap-1 px-3 py-2 text-xs text-on-surface-variant hover:text-on-surface transition-colors shrink-0"
          >
            <span className="material-symbols-outlined text-sm">close</span>
            Close
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0">
          {!activeSession || activeSession.messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center gap-3">
              <div className="flex items-center gap-1">
                {(activeSession?.advisor_ids ?? []).map(id => {
                  const m = AGENT_META[id]
                  return (
                    <div key={id} className={`w-9 h-9 rounded-xl flex items-center justify-center ${m?.iconBg}`}>
                      <span className={`material-symbols-outlined text-lg ${m?.iconColor}`}
                        style={{ fontVariationSettings: "'FILL' 1" }}>
                        {m?.icon ?? "smart_toy"}
                      </span>
                    </div>
                  )
                })}
              </div>
              <p className="text-sm text-on-surface font-medium">
                Consulting with {activeSession?.name ?? "…"}
              </p>
              <p className="text-xs text-on-surface-variant">Ask anything about strategy, product, tech, or growth.</p>
            </div>
          ) : (
            activeSession.messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} gap-2`}>
                {msg.role === "assistant" && (
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-1 ${AGENT_META[msg.advisor_id ?? ""]?.iconBg ?? "bg-surface-container"}`}>
                    <span className={`material-symbols-outlined text-sm ${AGENT_META[msg.advisor_id ?? ""]?.iconColor ?? "text-on-surface-variant"}`}
                      style={{ fontVariationSettings: "'FILL' 1" }}>
                      {AGENT_META[msg.advisor_id ?? ""]?.icon ?? "smart_toy"}
                    </span>
                  </div>
                )}
                <div className={`max-w-[72%] ${msg.role === "user" ? "" : ""}`}>
                  {msg.role === "assistant" && (
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 mb-1">
                      {AGENT_META[msg.advisor_id ?? ""]?.displayName ?? msg.advisor_id}
                    </p>
                  )}
                  <div className={`px-4 py-3 rounded-xl text-sm leading-relaxed whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "text-white rounded-br-sm"
                      : "bg-surface-container text-on-surface rounded-bl-sm"
                  }`}
                    style={msg.role === "user" ? {
                      background: "linear-gradient(135deg, #003d9b 0%, #0052cc 100%)"
                    } : undefined}
                  >
                    {msg.content}
                  </div>
                </div>
              </div>
            ))
          )}
          {activeSession?.loading && (
            <div className="flex justify-start gap-2">
              <div className="bg-surface-container px-4 py-3 rounded-xl text-sm text-on-surface-variant flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-outline animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-outline animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-outline animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-4 pb-5 pt-3 border-t border-surface-container shrink-0">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
              placeholder={`Message ${activeSession?.name ?? "agents"}…`}
              className="flex-1 px-4 py-3 bg-surface-container-low rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 border-none placeholder:text-on-surface-variant/60"
              disabled={activeSession?.loading}
            />
            <button
              onClick={send}
              disabled={!input.trim() || activeSession?.loading}
              className="w-11 h-11 flex items-center justify-center rounded-xl text-white disabled:opacity-40 transition-all hover:brightness-110 active:scale-95"
              style={{ background: "linear-gradient(135deg, #003d9b 0%, #0052cc 100%)" }}
            >
              <span className="material-symbols-outlined text-lg">send</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Agents Tab
// ─────────────────────────────────────────────────────────────────────────────

function AgentsTab() {
  const queryClient = useQueryClient()
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set())
  const [promptAdvisorId, setPromptAdvisorId] = useState<string | null>(null)
  const [proposalsAdvisorId, setProposalsAdvisorId] = useState<string | null>(null)
  const [settingsAdvisorId, setSettingsAdvisorId] = useState<string | null>(null)
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([])
  const [activeChatId, setActiveChatId] = useState<string | null>(null)
  const [showChat, setShowChat] = useState(false)
  const [runningSkill, setRunningSkill] = useState<string | null>(null)
  const [triggerResult, setTriggerResult] = useState<{ type: "success" | "error"; msg: string } | null>(null)
  const [showDiag, setShowDiag] = useState(false)

  const { data: advisors = [] } = useQuery<AdvisorConfig[]>({
    queryKey: ["strategy_advisors"],
    queryFn: fetchAdvisors,
    staleTime: 5 * 60_000,
  })

  const { data: proposals = [] } = useQuery<AdvisoryProposal[]>({
    queryKey: ["strategy_proposals"],
    queryFn: () => fetchProposals({ status: "pending_review" }),
    refetchInterval: 30_000,
  })

  const { data: recentRuns = [], refetch: refetchRuns } = useQuery<AdvisoryProposal[]>({
    queryKey: ["advisor_runs"],
    queryFn: () => fetchAdvisorRuns(10),
    refetchInterval: 60_000,
  })

  const { data: diag, refetch: refetchDiag, isFetching: diagLoading } = useQuery<Record<string, unknown>>({
    queryKey: ["advisor_diagnostics"],
    queryFn: fetchAdvisorDiagnostics,
    enabled: showDiag,
    staleTime: 0,
  })

  // Ensure all 4 advisors are shown even before API loads (use static meta as fallback)
  const allAdvisors: AdvisorConfig[] = AGENT_ORDER.map(id => {
    const found = advisors.find(a => a.id === id)
    return found ?? {
      id,
      model: "claude-sonnet-4-6",
      capabilities: AGENT_META[id]?.skills.filter(s => !s.todo).map(s => s.name) ?? [],
      prompt_ref: `${id}_v1`,
      system_prompt: "",
    }
  })

  const promptAdvisor = promptAdvisorId ? allAdvisors.find(a => a.id === promptAdvisorId) : null
  const settingsAdvisor = settingsAdvisorId ? allAdvisors.find(a => a.id === settingsAdvisorId) : null

  function toggleAgent(id: string) {
    setSelectedAgents(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function startConsultation() {
    if (selectedAgents.size === 0) return
    if (chatSessions.length >= MAX_CHAT_SESSIONS) {
      alert(`Maximum ${MAX_CHAT_SESSIONS} active chats. Close one to start a new consultation.`)
      return
    }
    const ids = Array.from(selectedAgents)
    const name = ids.map(id => AGENT_META[id]?.displayName ?? id).join(" & ")
    const session: ChatSession = {
      id: crypto.randomUUID(),
      name,
      advisor_ids: ids,
      messages: [],
      loading: false,
    }
    setChatSessions(prev => [...prev, session])
    setActiveChatId(session.id)
    setShowChat(true)
    setSelectedAgents(new Set())
  }

  const sendMessage = useCallback(async (sessionId: string, text: string) => {
    setChatSessions(prev => prev.map(s => {
      if (s.id !== sessionId) return s
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        ts: Date.now(),
      }
      return { ...s, messages: [...s.messages, userMsg], loading: true }
    }))

    // Build API payload from the session state BEFORE optimistic update
    setChatSessions(prev => {
      const session = prev.find(s => s.id === sessionId)
      if (!session) return prev

      const payload = session.messages.map(m => ({
        role: m.role as "user" | "assistant",
        content: m.content,
        advisor_id: m.advisor_id,
      }))
      // Add current user message
      payload.push({ role: "user" as const, content: text, advisor_id: undefined })

      chatWithAdvisors({ advisor_ids: session.advisor_ids, messages: payload })
        .then(resp => {
          setChatSessions(curr => curr.map(s => {
            if (s.id !== sessionId) return s
            const newMsgs: ChatMessage[] = resp.responses.map(r => ({
              id: crypto.randomUUID(),
              role: "assistant" as const,
              advisor_id: r.advisor_id,
              content: r.content,
              ts: Date.now(),
            }))
            return { ...s, messages: [...s.messages, ...newMsgs], loading: false }
          }))
        })
        .catch(err => {
          setChatSessions(curr => curr.map(s => {
            if (s.id !== sessionId) return s
            const errMsg: ChatMessage = {
              id: crypto.randomUUID(),
              role: "assistant",
              content: `Error: ${err.message}`,
              ts: Date.now(),
            }
            return { ...s, messages: [...s.messages, errMsg], loading: false }
          }))
        })

      return prev
    })
  }, [])

  function closeSession(id: string) {
    setChatSessions(prev => {
      const next = prev.filter(s => s.id !== id)
      if (activeChatId === id) setActiveChatId(next[0]?.id ?? null)
      if (next.length === 0) setShowChat(false)
      return next
    })
  }

  async function handleTriggerSkill(advisorId: string, skill: SkillDef) {
    if (skill.todo) return
    const key = `${advisorId}:${skill.name}`
    setRunningSkill(key)
    setTriggerResult(null)
    try {
      const resp = await triggerAdvisor(advisorId)
      queryClient.invalidateQueries({ queryKey: ["strategy_proposals"] })
      refetchRuns()
      const p = resp.proposal
      setTriggerResult({
        type: "success",
        msg: p
          ? `${AGENT_META[advisorId]?.displayName ?? advisorId} created proposal: "${p.category}" (priority ${p.priority})`
          : `${AGENT_META[advisorId]?.displayName ?? advisorId} completed successfully.`,
      })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error"
      setTriggerResult({ type: "error", msg })
      // errors stay until dismissed; only auto-clear success
    } finally {
      setRunningSkill(null)
    }
    // auto-dismiss success after 10s
    setTriggerResult(prev => prev?.type === "success" ? prev : prev)
    setTimeout(() => setTriggerResult(prev => prev?.type === "success" ? null : prev), 10_000)
  }

  return (
    <>
      {/* Trigger result toast */}
      {triggerResult && (
        <div className={`fixed top-20 right-6 z-50 max-w-sm w-full rounded-xl shadow-float px-5 py-4 flex items-start gap-3 transition-all ${
          triggerResult.type === "success"
            ? "bg-emerald-50 border border-emerald-200"
            : "bg-red-50 border border-red-200"
        }`}>
          <span className={`material-symbols-outlined text-lg shrink-0 mt-0.5 ${
            triggerResult.type === "success" ? "text-emerald-600" : "text-red-600"
          }`} style={{ fontVariationSettings: "'FILL' 1" }}>
            {triggerResult.type === "success" ? "check_circle" : "error"}
          </span>
          <p className={`text-sm font-medium leading-snug ${
            triggerResult.type === "success" ? "text-emerald-800" : "text-red-800"
          }`}>{triggerResult.msg}</p>
          <button onClick={() => setTriggerResult(null)} className="ml-auto shrink-0 text-on-surface-variant hover:text-on-surface">
            <span className="material-symbols-outlined text-sm">close</span>
          </button>
        </div>
      )}

      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-10">
        <div>
          <h3 className="text-3xl font-extrabold font-headline text-on-surface tracking-tight mb-1">Agent Roster</h3>
          <p className="text-on-surface-variant text-sm font-label">Configure and deploy specialized AI agents to execute your venture strategy.</p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {selectedAgents.size > 0 && (
            <button
              onClick={startConsultation}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm text-white shadow-float hover:brightness-110 transition-all"
              style={{ background: "linear-gradient(135deg, #003d9b 0%, #0052cc 100%)" }}
            >
              <span className="material-symbols-outlined text-sm">chat</span>
              Start Consultation ({selectedAgents.size})
            </button>
          )}
          {chatSessions.length > 0 && (
            <button
              onClick={() => setShowChat(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-outline-variant/40 text-sm font-medium hover:bg-surface-container transition-all"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
              </span>
              {chatSessions.length} Active Chat{chatSessions.length !== 1 ? "s" : ""}
            </button>
          )}
        </div>
      </div>

      {/* Agent cards grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {allAdvisors.map(advisor => (
          <AgentCard
            key={advisor.id}
            advisor={advisor}
            proposals={proposals}
            selected={selectedAgents.has(advisor.id)}
            runningSkill={runningSkill}
            onToggleSelect={() => toggleAgent(advisor.id)}
            onPrompt={() => setPromptAdvisorId(advisor.id)}
            onProposals={() => setProposalsAdvisorId(advisor.id)}
            onSettings={() => setSettingsAdvisorId(advisor.id)}
            onTriggerSkill={skill => handleTriggerSkill(advisor.id, skill)}
          />
        ))}
      </div>

      {/* Run history — always visible */}
      <div className="mt-10 bg-surface-container-lowest rounded-2xl shadow-card overflow-hidden">
        <div className="px-6 py-4 border-b border-surface-container flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center">
              <span className="material-symbols-outlined text-sm text-on-surface-variant">history</span>
            </div>
            <h3 className="text-sm font-bold font-headline text-on-surface">Recent Agent Runs</h3>
            {recentRuns.length > 0 && (
              <span className="text-xs text-on-surface-variant">({recentRuns.length})</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => { setShowDiag(v => !v); if (!showDiag) refetchDiag() }}
              className="text-xs text-on-surface-variant hover:text-on-surface font-medium flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-sm">bug_report</span>
              Diagnostics
            </button>
            <button onClick={() => refetchRuns()} className="text-xs text-primary hover:underline font-medium">Refresh</button>
          </div>
        </div>

        {/* Diagnostics panel */}
        {showDiag && (
          <div className="px-6 py-4 bg-slate-950 text-slate-300 text-xs font-mono border-b border-surface-container">
            {diagLoading ? (
              <span className="text-slate-400">Loading diagnostics…</span>
            ) : diag ? (
              <div className="space-y-1">
                {Object.entries(diag).map(([k, v]) => (
                  <div key={k}>
                    <span className="text-slate-500">{k}: </span>
                    <span className={
                      v === true ? "text-emerald-400" :
                      v === false ? "text-red-400" :
                      typeof v === "string" && v.startsWith("error") ? "text-red-400" :
                      "text-slate-200"
                    }>
                      {typeof v === "object" ? JSON.stringify(v, null, 2) : String(v)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <span className="text-slate-400">No data</span>
            )}
          </div>
        )}

        {recentRuns.length === 0 ? (
          <div className="px-6 py-10 text-center">
            <span className="material-symbols-outlined text-3xl text-on-surface-variant/40 block mb-2">history</span>
            <p className="text-sm text-on-surface-variant">No runs yet. Click a skill button to trigger an agent.</p>
            <p className="text-xs text-on-surface-variant/60 mt-1">Click "Diagnostics" above to check DB and API connectivity.</p>
          </div>
        ) : (
          <div className="divide-y divide-surface-container">
            {recentRuns.map(run => {
              const meta = AGENT_META[run.advisor_id]
              return (
                <div key={String(run.id)} className="flex items-center gap-4 px-6 py-3">
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${meta?.iconBg ?? "bg-surface-container"}`}>
                    <span className={`material-symbols-outlined text-sm ${meta?.iconColor ?? "text-on-surface-variant"}`}
                      style={{ fontVariationSettings: "'FILL' 1" }}>
                      {meta?.icon ?? "smart_toy"}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-on-surface truncate">
                      {meta?.displayName ?? run.advisor_id}
                      <span className="text-on-surface-variant font-normal ml-2">— {run.category}</span>
                    </p>
                    <p className="text-xs text-on-surface-variant truncate">
                      {typeof run.content === "object" && run.content !== null
                        ? (run.content as Record<string, string>).summary ?? JSON.stringify(run.content).slice(0, 100)
                        : String(run.content).slice(0, 100)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      run.status === "pending_review" ? "bg-yellow-100 text-yellow-700" :
                      run.status === "approved" ? "bg-emerald-100 text-emerald-700" :
                      run.status === "rejected" ? "bg-red-100 text-red-700" :
                      "bg-surface-container text-on-surface-variant"
                    }`}>{run.status.replace("_", " ")}</span>
                    <span className="text-xs text-on-surface-variant">
                      {new Date(run.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Ongoing chats indicator (bottom bar) */}
      {chatSessions.length > 0 && !showChat && (
        <div className="mt-10 bg-surface-container-low rounded-xl px-6 py-4 flex items-center justify-between border border-outline-variant/20">
          <div className="flex items-center gap-3">
            <div className="relative">
              <span className="w-3 h-3 bg-green-500 rounded-full block" />
              <span className="absolute inset-0 w-3 h-3 bg-green-400 rounded-full animate-ping" />
            </div>
            <div>
              <p className="text-sm font-bold font-headline text-on-surface">Ongoing Consultations</p>
              <p className="text-xs text-on-surface-variant">
                {chatSessions.map(s => s.name).join(" · ")}
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowChat(true)}
            className="text-primary text-sm font-bold hover:underline transition-all"
          >
            View Chat Stream
          </button>
        </div>
      )}

      {/* Modals */}
      {promptAdvisor && (
        <AgentPromptEditor
          advisor={promptAdvisor}
          onClose={() => setPromptAdvisorId(null)}
        />
      )}

      {proposalsAdvisorId && (
        <ProposalsDialog
          advisorId={proposalsAdvisorId}
          proposals={proposals}
          onClose={() => setProposalsAdvisorId(null)}
        />
      )}

      {settingsAdvisor && (
        <AgentSettingsDialog
          advisor={settingsAdvisor}
          onClose={() => setSettingsAdvisorId(null)}
          onEditPrompt={() => setPromptAdvisorId(settingsAdvisor.id)}
        />
      )}

      {/* Chat drawer */}
      {showChat && chatSessions.length > 0 && (
        <ChatPanel
          sessions={chatSessions}
          activeId={activeChatId}
          onSelectSession={setActiveChatId}
          onCloseSession={closeSession}
          onSendMessage={sendMessage}
          onClose={() => setShowChat(false)}
        />
      )}
    </>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Roadmap Tab (unchanged logic, minimal styling tweaks for new design)
// ─────────────────────────────────────────────────────────────────────────────

interface ItemFormProps {
  item: Partial<RoadmapItem> | null
  features: RoadmapFeature[]
  onSave: (data: {
    title: string; description: string
    item_type: RoadmapItemType; feature_id: number | null; status: RoadmapStatus
  }) => void
  onCancel: () => void
  onAddFeature: (name: string) => Promise<RoadmapFeature>
  isSaving: boolean
}

function ItemForm({ item, features, onSave, onCancel, onAddFeature, isSaving }: ItemFormProps) {
  const isNew = !item?.id
  const [title, setTitle] = useState(item?.title ?? "")
  const [description, setDescription] = useState(item?.description ?? "")
  const [itemType, setItemType] = useState<RoadmapItemType>(item?.item_type ?? "New feature")
  const [featureId, setFeatureId] = useState<number | null>(item?.feature_id ?? null)
  const [status, setStatus] = useState<RoadmapStatus>(item?.status ?? "not_started")
  const [addingFeature, setAddingFeature] = useState(false)
  const [newFeatureName, setNewFeatureName] = useState("")
  const [featureError, setFeatureError] = useState("")

  async function handleFeatureChange(val: string) {
    if (val === "__add__") { setAddingFeature(true); return }
    setFeatureId(val ? parseInt(val) : null)
  }

  async function confirmNewFeature() {
    const name = newFeatureName.trim()
    if (!name) return
    setFeatureError("")
    try {
      const feat = await onAddFeature(name)
      setFeatureId(feat.id)
      setNewFeatureName("")
      setAddingFeature(false)
    } catch {
      setFeatureError("Could not add feature — it may already exist.")
    }
  }

  function handleSubmit() {
    if (!title.trim()) return
    onSave({ title: title.trim(), description, item_type: itemType, feature_id: featureId, status })
  }

  const inputCls = "w-full bg-surface-container-low border-none rounded-xl px-4 py-2.5 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant/50"

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-surface-container-lowest rounded-2xl shadow-float w-full max-w-lg mx-4 p-6">
        <h2 className="text-lg font-bold font-headline text-on-surface mb-5">
          {isNew ? "Add Backlog Item" : "Edit Item"}
        </h2>

        <div className="space-y-4">
          {!isNew && (
            <div className="flex items-center gap-2 text-sm text-on-surface-variant">
              <span className="font-medium">ID:</span>
              <span className="font-mono bg-surface-container px-2 py-0.5 rounded-lg text-on-surface-variant">#{item?.id}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 mb-1.5">
              Title *
            </label>
            <input type="text" maxLength={100} value={title} onChange={e => setTitle(e.target.value)}
              className={inputCls} placeholder="Short title (max 100 chars)" />
            <p className="text-xs text-on-surface-variant/50 mt-1">{title.length}/100</p>
          </div>

          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 mb-1.5">Type</label>
            <select value={itemType} onChange={e => setItemType(e.target.value as RoadmapItemType)} className={inputCls}>
              {ITEM_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 mb-1.5">Feature</label>
            {addingFeature ? (
              <div className="flex gap-2">
                <input type="text" value={newFeatureName} onChange={e => setNewFeatureName(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && confirmNewFeature()}
                  className={inputCls + " flex-1"} placeholder="New feature name" autoFocus />
                <button onClick={confirmNewFeature} className="px-3 py-2 bg-primary text-on-primary text-sm rounded-xl font-medium">Add</button>
                <button onClick={() => { setAddingFeature(false); setNewFeatureName("") }}
                  className="px-3 py-2 bg-surface-container text-on-surface text-sm rounded-xl font-medium">Cancel</button>
              </div>
            ) : (
              <select value={featureId ?? ""} onChange={e => handleFeatureChange(e.target.value)} className={inputCls}>
                <option value="">— None —</option>
                {features.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                <option value="__add__">+ Add feature…</option>
              </select>
            )}
            {featureError && <p className="text-xs text-error mt-1">{featureError}</p>}
          </div>

          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 mb-1.5">Description</label>
            <textarea maxLength={500} value={description} onChange={e => setDescription(e.target.value)}
              rows={3} className={inputCls + " resize-none"} placeholder="Optional description (max 500 chars)" />
            <p className="text-xs text-on-surface-variant/50 mt-1">{description.length}/500</p>
          </div>

          {!isNew && (
            <div>
              <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 mb-1.5">Status</label>
              <select value={status} onChange={e => setStatus(e.target.value as RoadmapStatus)} className={inputCls}>
                {ALL_STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
              </select>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-surface-container">
          <button onClick={onCancel}
            className="px-4 py-2 border border-outline-variant/40 text-on-surface rounded-xl text-sm font-medium hover:bg-surface-container transition-all">
            Cancel
          </button>
          <button onClick={handleSubmit} disabled={isSaving || !title.trim()}
            className="px-4 py-2 rounded-xl text-sm font-bold text-white disabled:opacity-50 hover:brightness-110 transition-all"
            style={{ background: "linear-gradient(135deg, #003d9b 0%, #0052cc 100%)" }}>
            {isSaving ? "Saving…" : isNew ? "Add to Backlog" : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  )
}

function RecentlyDoneModal({ items, onClose }: { items: RoadmapItem[]; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-surface-container-lowest rounded-2xl shadow-float w-full max-w-xl mx-4 p-6">
        <div className="flex justify-between items-center mb-5">
          <h2 className="text-lg font-bold font-headline text-on-surface">Recently Done — last 30 days</h2>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface p-1">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>
        {items.length === 0 ? (
          <p className="text-on-surface-variant italic py-8 text-center text-sm">No items completed in the last 30 days.</p>
        ) : (
          <div className="space-y-2">
            {items.map(item => (
              <div key={item.id} className="flex items-center gap-3 px-4 py-3 bg-surface-container-low rounded-xl text-sm">
                <span className="text-xs text-on-surface-variant w-8 shrink-0">#{item.id}</span>
                <span className="flex-1 text-on-surface font-medium">{item.title}</span>
                <span className="text-on-surface-variant shrink-0">
                  {item.completed_at ? new Date(item.completed_at).toLocaleDateString() : "—"}
                </span>
              </div>
            ))}
          </div>
        )}
        <div className="flex justify-end mt-5">
          <button onClick={onClose}
            className="px-4 py-2 border border-outline-variant/40 text-on-surface rounded-xl text-sm font-medium hover:bg-surface-container transition-all">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

interface ItemRowProps {
  item: RoadmapItem; canDelete: boolean
  onEdit: (item: RoadmapItem) => void; onDelete: (id: number) => void
  onDragStart: (id: number) => void; onDragOver: (e: React.DragEvent, id: number) => void
  onDrop: () => void; isDragOver: boolean
}

function ItemRow({ item, canDelete, onEdit, onDelete, onDragStart, onDragOver, onDrop, isDragOver }: ItemRowProps) {
  return (
    <div
      draggable
      onDragStart={() => onDragStart(item.id)}
      onDragOver={e => { e.preventDefault(); onDragOver(e, item.id) }}
      onDrop={onDrop}
      className={`flex items-start gap-3 px-4 py-3 bg-surface-container-lowest rounded-xl transition-all cursor-grab active:cursor-grabbing select-none
        ${isDragOver ? "ring-2 ring-primary/30 shadow-float" : "shadow-card hover:shadow-float"}`}
    >
      <div className="mt-1 text-on-surface-variant/30 hover:text-on-surface-variant/60 shrink-0" title="Drag to reorder">
        <svg width="12" height="12" viewBox="0 0 14 14" fill="currentColor">
          <circle cx="4" cy="3" r="1.2"/><circle cx="10" cy="3" r="1.2"/>
          <circle cx="4" cy="7" r="1.2"/><circle cx="10" cy="7" r="1.2"/>
          <circle cx="4" cy="11" r="1.2"/><circle cx="10" cy="11" r="1.2"/>
        </svg>
      </div>
      <span className="text-xs text-on-surface-variant mt-0.5 shrink-0 w-8 font-mono">#{item.id}</span>
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-1.5 mb-1">
          <span className="font-medium text-on-surface text-sm">{item.title}</span>
          {item.item_type && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_COLOURS[item.item_type] ?? "bg-surface-container text-on-surface-variant"}`}>
              {item.item_type}
            </span>
          )}
          {item.feature_name && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-medium">
              {item.feature_name}
            </span>
          )}
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOURS[item.status] ?? "bg-surface-container text-on-surface-variant"}`}>
            {STATUS_LABELS[item.status]}
          </span>
        </div>
        {item.description && <p className="text-xs text-on-surface-variant line-clamp-2">{item.description}</p>}
      </div>
      <div className="flex gap-1.5 shrink-0">
        <button onClick={() => onEdit(item)}
          className="text-xs px-2.5 py-1.5 border border-outline-variant/40 rounded-lg text-on-surface-variant hover:bg-surface-container transition-all">
          Edit
        </button>
        {canDelete && (
          <button onClick={() => onDelete(item.id)}
            className="text-xs px-2.5 py-1.5 border border-error/30 rounded-lg text-error hover:bg-error-container transition-all">
            Delete
          </button>
        )}
      </div>
    </div>
  )
}

function RoadmapTab() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState<RoadmapItem | null>(null)
  const [showDone, setShowDone] = useState(false)
  const draggedId = useRef<number | null>(null)
  const dragOverId = useRef<number | null>(null)
  const [dragOverItemId, setDragOverItemId] = useState<number | null>(null)

  const { data: roadmap, isLoading } = useQuery({ queryKey: ["roadmap"], queryFn: fetchRoadmap })
  const { data: features = [] } = useQuery({ queryKey: ["roadmap_features"], queryFn: fetchRoadmapFeatures })
  const { data: doneItems = [], refetch: refetchDone } = useQuery({
    queryKey: ["roadmap_done"], queryFn: fetchRoadmapDone, enabled: false,
  })

  const createFeatureMutation = useMutation({
    mutationFn: (name: string) => createRoadmapFeature(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["roadmap_features"] }),
  })
  const createMutation = useMutation({
    mutationFn: createRoadmapItem,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["roadmap"] }); setShowForm(false) },
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof updateRoadmapItem>[1] }) =>
      updateRoadmapItem(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["roadmap"] }); setEditingItem(null); setShowForm(false) },
  })
  const deleteMutation = useMutation({
    mutationFn: deleteRoadmapItem,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["roadmap"] }),
  })
  const reorderMutation = useMutation({
    mutationFn: reorderRoadmapItems,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["roadmap"] }),
  })

  function handleSave(data: Parameters<typeof createMutation.mutate>[0]) {
    if (editingItem) updateMutation.mutate({ id: editingItem.id, data })
    else createMutation.mutate(data)
  }

  function handleDelete(id: number) {
    if (!window.confirm("Delete this item?")) return
    deleteMutation.mutate(id)
  }

  function handleDrop(section: "backlog" | "wip") {
    const from = draggedId.current
    const to = dragOverId.current
    if (from === null || to === null || from === to) {
      draggedId.current = null; dragOverId.current = null; setDragOverItemId(null); return
    }
    const list = section === "backlog" ? (roadmap?.backlog ?? []) : (roadmap?.wip ?? [])
    const ids = list.map(i => i.id)
    const fi = ids.indexOf(from), ti = ids.indexOf(to)
    if (fi === -1 || ti === -1) return
    ids.splice(fi, 1); ids.splice(ti, 0, from)
    reorderMutation.mutate(ids)
    draggedId.current = null; dragOverId.current = null; setDragOverItemId(null)
  }

  async function handleShowDone() { await refetchDone(); setShowDone(true) }

  if (isLoading) return (
    <div className="flex items-center justify-center py-16 text-on-surface-variant text-sm">Loading roadmap…</div>
  )

  const backlog = roadmap?.backlog ?? []
  const wip = roadmap?.wip ?? []

  return (
    <div className="space-y-10">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h3 className="text-3xl font-extrabold font-headline text-on-surface tracking-tight mb-1">Product Roadmap</h3>
          <p className="text-on-surface-variant text-sm font-label">
            {backlog.length} in backlog · {wip.length} in progress
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={handleShowDone}
            className="px-4 py-2.5 border border-outline-variant/40 text-on-surface text-sm font-medium rounded-xl hover:bg-surface-container transition-all"
          >
            <span className="material-symbols-outlined text-sm align-middle mr-1.5">history</span>
            Recently Done
          </button>
          <button
            onClick={() => { setEditingItem(null); setShowForm(true) }}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white shadow-float hover:brightness-110 transition-all"
            style={{ background: "linear-gradient(135deg, #003d9b 0%, #0052cc 100%)" }}
          >
            <span className="material-symbols-outlined text-sm">add</span>
            Add Item
          </button>
        </div>
      </div>

      {/* WIP section */}
      <section className="bg-surface-container-lowest rounded-2xl shadow-card p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>
              trending_up
            </span>
          </div>
          <div>
            <h2 className="text-lg font-bold font-headline text-on-surface">Work in Progress</h2>
            <p className="text-xs text-on-surface-variant">{wip.length} active item{wip.length !== 1 ? "s" : ""} · drag to reorder</p>
          </div>
        </div>
        {wip.length === 0 ? (
          <div className="text-on-surface-variant italic text-sm py-10 text-center bg-surface-container-low rounded-xl">
            No items in progress.
          </div>
        ) : (
          <div className="space-y-2">
            {wip.map(item => (
              <ItemRow key={item.id} item={item} canDelete={false}
                onEdit={i => { setEditingItem(i); setShowForm(true) }}
                onDelete={handleDelete}
                onDragStart={id => { draggedId.current = id }}
                onDragOver={(e, id) => { e.preventDefault(); dragOverId.current = id; setDragOverItemId(id) }}
                onDrop={() => handleDrop("wip")}
                isDragOver={dragOverItemId === item.id} />
            ))}
          </div>
        )}
      </section>

      {/* Backlog section */}
      <section className="bg-surface-container-lowest rounded-2xl shadow-card p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-surface-container flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-on-surface-variant" style={{ fontVariationSettings: "'FILL' 1" }}>
              format_list_bulleted
            </span>
          </div>
          <div>
            <h2 className="text-lg font-bold font-headline text-on-surface">Product Backlog</h2>
            <p className="text-xs text-on-surface-variant">{backlog.length} item{backlog.length !== 1 ? "s" : ""} queued · drag to prioritize</p>
          </div>
        </div>
        {backlog.length === 0 ? (
          <div className="text-on-surface-variant italic text-sm py-10 text-center bg-surface-container-low rounded-xl border-2 border-dashed border-outline-variant/40">
            No backlog items yet. Click "+ Add Item" to start building your roadmap.
          </div>
        ) : (
          <div className="space-y-2">
            {backlog.map(item => (
              <ItemRow key={item.id} item={item} canDelete
                onEdit={i => { setEditingItem(i); setShowForm(true) }}
                onDelete={handleDelete}
                onDragStart={id => { draggedId.current = id }}
                onDragOver={(e, id) => { e.preventDefault(); dragOverId.current = id; setDragOverItemId(id) }}
                onDrop={() => handleDrop("backlog")}
                isDragOver={dragOverItemId === item.id} />
            ))}
          </div>
        )}
      </section>

      {showForm && (
        <ItemForm item={editingItem} features={features}
          onSave={handleSave}
          onCancel={() => { setShowForm(false); setEditingItem(null) }}
          onAddFeature={name => createFeatureMutation.mutateAsync(name)}
          isSaving={createMutation.isPending || updateMutation.isPending} />
      )}
      {showDone && <RecentlyDoneModal items={doneItems} onClose={() => setShowDone(false)} />}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────

// ── Market Research Tab ────────────────────────────────────────────────────────

const LLM_META: Record<string, { label: string; color: string; bg: string }> = {
  claude: { label: "Claude",  color: "text-violet-700",  bg: "bg-violet-100" },
  openai: { label: "OpenAI",  color: "text-emerald-700", bg: "bg-emerald-100" },
  gemini: { label: "Gemini",  color: "text-blue-700",    bg: "bg-blue-100" },
  grok:   { label: "Grok",    color: "text-orange-700",  bg: "bg-orange-100" },
}

const MR_STATUS_LABELS: Record<string, string> = {
  pending:        "Pending",
  optimizing:     "Optimizing prompts…",
  researching:    "Researching…",
  merging:        "Merging reports…",
  reflecting:     "Critic reviewing…",
  generating_pdf: "Generating PDF…",
  pdf_ready:      "PDF ready",
  delivering:     "Delivering…",
  delivered:      "Delivered",
  failed:         "Failed",
}

function MrStatusBadge({ status }: { status: string }) {
  const active = ["optimizing","researching","merging","reflecting","generating_pdf","delivering"].includes(status)
  const done   = ["pdf_ready","delivered"].includes(status)
  const failed = status === "failed"
  const cls = active ? "bg-blue-100 text-blue-700 animate-pulse"
             : done   ? "bg-green-100 text-green-700"
             : failed ? "bg-red-100 text-red-700"
             :          "bg-gray-100 text-gray-600"
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {MR_STATUS_LABELS[status] ?? status}
    </span>
  )
}

function SessionDetailDrawer({
  session,
  isLoading,
  onClose,
  onRerun,
  onRetry,
}: {
  session: MarketResearchDetail | null
  isLoading: boolean
  onClose: () => void
  onRerun: (topic: string, prompts: Record<string, string>, selectedLlms: string[], criticLlm: string) => void
  onRetry: () => void
}) {
  const [tab, setTab] = useState<"report" | "critic" | "prompts">("report")
  const [rerunMode, setRerunMode] = useState(false)
  const [editedPrompts, setEditedPrompts] = useState<Record<string, string>>({})
  const [retrying, setRetrying] = useState(false)

  useEffect(() => {
    if (session?.optimized_prompts) setEditedPrompts({ ...session.optimized_prompts })
  }, [session?.optimized_prompts])

  const isDone = session ? ["pdf_ready", "delivered", "failed"].includes(session.status) : false
  const canRetry = session ? ["failed", "pending"].includes(session.status) : false

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">

        {/* Header — fixed, never clips */}
        <div className="flex items-start gap-3 px-6 pt-5 pb-4 border-b shrink-0">
          <div className="flex-1 min-w-0">
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">Research Session</p>
            {isLoading || !session
              ? <div className="h-5 w-48 bg-gray-100 rounded animate-pulse" />
              : <h3 className="font-semibold text-gray-900 text-base leading-snug break-words">{session.title || session.topic}</h3>
            }
            <div className="mt-1.5 flex items-center gap-2 flex-wrap">
              {session && <MrStatusBadge status={session.status} />}
              {session?.drive_link && (
                <a href={session.drive_link} target="_blank" rel="noopener noreferrer"
                   className="inline-flex items-center gap-1 text-xs text-primary font-medium hover:underline">
                  <span className="material-symbols-outlined text-sm">download</span>
                  Download PDF
                </a>
              )}
            </div>
          </div>
          {/* Close button — always visible, separate from content */}
          <button
            onClick={onClose}
            className="shrink-0 mt-0.5 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
            aria-label="Close"
          >
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b px-6 gap-4 shrink-0">
          {(["report", "critic", "prompts"] as const).map(t => (
            <button key={t} onClick={() => { setTab(t); setRerunMode(false) }}
              className={`py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === t ? "border-primary text-primary" : "border-transparent text-gray-500 hover:text-gray-800"
              }`}>
              {t === "report" ? "Report" : t === "critic" ? "Critic Feedback" : "Optimized Prompts"}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 text-sm text-gray-700 leading-relaxed">
          {isLoading || !session ? (
            <div className="space-y-3 animate-pulse">
              <div className="h-4 bg-gray-100 rounded w-3/4" />
              <div className="h-4 bg-gray-100 rounded w-full" />
              <div className="h-4 bg-gray-100 rounded w-5/6" />
            </div>
          ) : (
            <>
              {tab === "report" && (
                <div className="whitespace-pre-wrap">{session.final_report || session.merged_report || "No report yet."}</div>
              )}

              {tab === "critic" && (
                <div className="whitespace-pre-wrap">{session.critic_feedback || "No critic feedback yet."}</div>
              )}

              {tab === "prompts" && (
                <div className="space-y-5">
                  {session.optimized_prompts
                    ? Object.entries(rerunMode ? editedPrompts : session.optimized_prompts).map(([llm, prompt]) => (
                        <div key={llm}>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mb-2 ${LLM_META[llm]?.bg ?? "bg-gray-100"} ${LLM_META[llm]?.color ?? "text-gray-700"}`}>
                            {LLM_META[llm]?.label ?? llm}
                            {session.critic_llm === llm && <span className="ml-1 opacity-70">★ Critic</span>}
                          </span>
                          {rerunMode ? (
                            <textarea
                              value={editedPrompts[llm] ?? prompt}
                              onChange={e => setEditedPrompts(prev => ({ ...prev, [llm]: e.target.value }))}
                              rows={6}
                              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 resize-y"
                            />
                          ) : (
                            <p className="text-xs text-gray-600 whitespace-pre-wrap bg-gray-50 rounded-lg p-3">{prompt}</p>
                          )}
                        </div>
                      ))
                    : <p className="text-gray-400">Prompts not yet generated.</p>
                  }
                </div>
              )}

              {session.error && (
                <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-xs">
                  <strong>Error:</strong> {session.error}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer actions — Retry (always visible for failed/pending) or Adjust & Rerun */}
        {canRetry && (
          <div className="shrink-0 px-6 py-4 border-t bg-red-50 rounded-b-2xl flex items-center justify-between gap-3">
            <p className="text-xs text-gray-500">
              {session?.status === "failed" ? "This session failed — retry to run it again." : "This session is stuck pending — retry to re-queue it."}
            </p>
            <button
              disabled={retrying}
              onClick={async () => {
                setRetrying(true)
                try { await onRetry() } finally { setRetrying(false) }
              }}
              className="shrink-0 flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-primary text-white font-medium hover:bg-primary/90 disabled:opacity-50">
              <span className="material-symbols-outlined text-sm">replay</span>
              {retrying ? "Retrying..." : "Retry Now"}
            </button>
          </div>
        )}

        {!canRetry && tab === "prompts" && session?.optimized_prompts && isDone && (
          <div className="shrink-0 px-6 py-4 border-t bg-gray-50 rounded-b-2xl flex items-center justify-between gap-3">
            {rerunMode ? (
              <>
                <p className="text-xs text-gray-500">Edit the prompts above, then rerun.</p>
                <div className="flex gap-2">
                  <button onClick={() => { setRerunMode(false); setEditedPrompts({ ...session.optimized_prompts! }) }}
                    className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 transition-colors">
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      onRerun(session.topic, editedPrompts, session.selected_llms, session.critic_llm)
                      onClose()
                    }}
                    className="px-4 py-2 text-sm rounded-lg bg-primary text-white font-semibold hover:bg-primary/90 transition-colors flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-sm">replay</span>
                    Rerun Research
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="text-xs text-gray-500">Adjust individual prompts and rerun the full pipeline.</p>
                <button onClick={() => setRerunMode(true)}
                  className="px-4 py-2 text-sm rounded-lg border border-primary text-primary font-medium hover:bg-primary/5 transition-colors flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-sm">edit</span>
                  Adjust & Rerun
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function MarketResearchTab() {
  const [topic, setTopic] = useState("")
  const [selectedLlms, setSelectedLlms] = useState<string[]>([])
  const [criticLlm, setCriticLlm] = useState("grok")
  const [email, setEmail] = useState("")
  const [files, setFiles] = useState<File[]>([])
  const [detailId, setDetailId] = useState<string | null>(null)
  const [pollingId, setPollingId] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  const { data: llmsData } = useQuery({ queryKey: ["market-research-llms"], queryFn: fetchAvailableLlms })
  const { data: sessions = [] } = useQuery({ queryKey: ["market-research-sessions"], queryFn: fetchMarketResearchSessions, refetchInterval: pollingId ? 3000 : false })
  const { data: detail, isLoading: isLoadingDetail } = useQuery({
    queryKey: ["market-research-session", detailId],
    queryFn: () => fetchMarketResearchSession(detailId!),
    enabled: !!detailId,
    refetchInterval: detailId && sessions.find(s => s.id === detailId && !["delivered","pdf_ready","failed"].includes(s.status)) ? 4000 : false,
  })

  const availableLlms = llmsData?.available ?? []

  useEffect(() => {
    if (availableLlms.length && selectedLlms.length === 0) {
      setSelectedLlms(availableLlms)
      if (availableLlms.includes("grok")) setCriticLlm("grok")
      else if (availableLlms.length > 0) setCriticLlm(availableLlms[availableLlms.length - 1])
    }
  }, [availableLlms])

  const createMutation = useMutation({
    mutationFn: async () => {
      const sess = await createMarketResearchSession({
        topic,
        selected_llms: selectedLlms,
        critic_llm: criticLlm,
        client_email: email || undefined,
      })
      if (files.length > 0) {
        await uploadResearchDocs(sess.id, files)
      }
      return sess
    },
    onSuccess: (sess) => {
      queryClient.invalidateQueries({ queryKey: ["market-research-sessions"] })
      setPollingId(sess.id)
      setTopic("")
      setFiles([])
      setEmail("")
    },
  })

  const toggleLlm = (llm: string) => {
    setSelectedLlms(prev =>
      prev.includes(llm) ? prev.filter(l => l !== llm) : [...prev, llm]
    )
  }

  const activeSession = sessions.find(s => pollingId && s.id === pollingId)
  useEffect(() => {
    if (activeSession && ["delivered","pdf_ready","failed"].includes(activeSession.status)) {
      setPollingId(null)
    }
  }, [activeSession])

  return (
    <div className="space-y-8">
      {/* Control Panel */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-5">
        <h3 className="font-semibold text-gray-900 text-base">New Research Session</h3>

        {/* Topic */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Research Topic</label>
          <textarea
            value={topic}
            onChange={e => setTopic(e.target.value)}
            rows={3}
            placeholder="e.g. 'Market opportunity for AI-powered podcast editing tools in 2025'"
            className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
          />
        </div>

        {/* LLM selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Research Committee</label>
          <div className="flex flex-wrap gap-2">
            {availableLlms.map(llm => {
              const meta = LLM_META[llm]
              const checked = selectedLlms.includes(llm)
              const isCritic = criticLlm === llm
              return (
                <button
                  key={llm}
                  onClick={() => toggleLlm(llm)}
                  className={`relative flex items-center gap-2 px-3 py-2 rounded-xl border text-sm font-medium transition-all ${
                    checked
                      ? `${meta?.bg ?? "bg-gray-100"} ${meta?.color ?? "text-gray-700"} border-current`
                      : "bg-gray-50 text-gray-400 border-gray-200"
                  }`}
                >
                  <span className={`w-4 h-4 rounded border-2 flex items-center justify-center ${checked ? "border-current bg-current" : "border-gray-300"}`}>
                    {checked && <span className="material-symbols-outlined text-white text-xs">check</span>}
                  </span>
                  {meta?.label ?? llm}
                  {isCritic && checked && (
                    <span className="ml-1 px-1.5 py-0.5 bg-white/60 text-xs rounded-full font-medium">Critic</span>
                  )}
                </button>
              )
            })}
          </div>
          {selectedLlms.length > 0 && (
            <div className="mt-3">
              <label className="block text-xs text-gray-500 mb-1">Critic Model</label>
              <div className="flex gap-2 flex-wrap">
                {selectedLlms.map(llm => (
                  <button key={llm} onClick={() => setCriticLlm(llm)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                      criticLlm === llm
                        ? `${LLM_META[llm]?.bg ?? "bg-gray-100"} ${LLM_META[llm]?.color ?? "text-gray-700"} border-current`
                        : "bg-white text-gray-500 border-gray-200 hover:border-gray-400"
                    }`}>
                    {LLM_META[llm]?.label ?? llm}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* File upload */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Supplementary Documents (optional)</label>
          <div
            className="border-2 border-dashed border-gray-300 rounded-xl px-4 py-5 text-center cursor-pointer hover:border-primary/50 transition-colors"
            onClick={() => fileRef.current?.click()}
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); setFiles(prev => [...prev, ...Array.from(e.dataTransfer.files)]) }}
          >
            <span className="material-symbols-outlined text-2xl text-gray-400">upload_file</span>
            <p className="text-sm text-gray-500 mt-1">Drag & drop or click to browse — PDF, Word, Excel, PowerPoint, TXT, MD</p>
            {files.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1 justify-center">
                {files.map((f, i) => (
                  <span key={i} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{f.name}</span>
                ))}
              </div>
            )}
          </div>
          <input ref={fileRef} type="file" multiple accept=".pdf,.txt,.md,.docx,.doc,.xlsx,.xls,.pptx,.ppt" className="hidden"
            onChange={e => setFiles(prev => [...prev, ...Array.from(e.target.files ?? [])])} />
        </div>

        {/* Email */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Delivery Email (optional)</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)}
            placeholder="client@example.com"
            className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
        </div>

        <button
          disabled={!topic.trim() || selectedLlms.length === 0 || createMutation.isPending}
          onClick={() => createMutation.mutate()}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-white rounded-xl text-sm font-semibold shadow hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <span className="material-symbols-outlined text-base">science</span>
          {createMutation.isPending ? "Starting…" : "Start Research"}
        </button>
        {createMutation.isError && (
          <p className="text-red-600 text-sm">{String((createMutation.error as Error)?.message)}</p>
        )}
      </div>

      {/* Sessions list */}
      <div>
        <h3 className="font-semibold text-gray-900 text-base mb-4">Research Sessions</h3>
        {sessions.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-12">No sessions yet. Start your first research above.</p>
        ) : (
          <div className="space-y-3">
            {sessions.map(sess => (
              <div key={sess.id}
                className="bg-white border border-gray-200 rounded-xl p-4 flex items-start justify-between gap-4 hover:border-gray-300 transition-colors cursor-pointer"
                onClick={() => { setDetailId(sess.id) }}>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 text-sm truncate">{sess.title || sess.topic}</p>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <MrStatusBadge status={sess.status} />
                    {sess.selected_llms.map(llm => (
                      <span key={llm} className={`text-xs px-1.5 py-0.5 rounded ${LLM_META[llm]?.bg ?? "bg-gray-100"} ${LLM_META[llm]?.color ?? "text-gray-600"}`}>
                        {LLM_META[llm]?.label ?? llm}
                        {sess.critic_llm === llm ? " ★" : ""}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {sess.drive_link && (
                    <a href={sess.drive_link} target="_blank" rel="noopener noreferrer"
                       onClick={e => e.stopPropagation()}
                       className="text-primary text-sm hover:underline flex items-center gap-0.5">
                      <span className="material-symbols-outlined text-sm">download</span>
                      PDF
                    </a>
                  )}
                  <span className="text-xs text-gray-400">{new Date(sess.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Detail drawer */}
      {detailId && (
        <SessionDetailDrawer
          session={detail ?? null}
          isLoading={isLoadingDetail}
          onClose={() => setDetailId(null)}
          onRerun={(_topic, prompts, llms, critic) => {
            rerunResearchSession(detailId!, prompts, llms, critic).then(sess => {
              queryClient.invalidateQueries({ queryKey: ["market-research-sessions"] })
              setPollingId(sess.id)
            })
          }}
          onRetry={async () => {
            await retryResearchSession(detailId!)
            queryClient.invalidateQueries({ queryKey: ["market-research-sessions"] })
            queryClient.invalidateQueries({ queryKey: ["market-research-session", detailId] })
            setPollingId(detailId)
          }}
        />
      )}
    </div>
  )
}

export default function StrategyRoom() {
  const [activeTab, setActiveTab] = useState<"agents" | "roadmap" | "market-research">("agents")

  const tabs: { key: "agents" | "roadmap" | "market-research"; label: string; icon: string }[] = [
    { key: "agents",          label: "Agents",          icon: "psychology" },
    { key: "roadmap",         label: "Roadmap",         icon: "map" },
    { key: "market-research", label: "Market Research", icon: "analytics" },
  ]

  return (
    <div className="min-h-screen bg-surface">
      {/* Top header bar */}
      <header className="sticky top-0 z-30 bg-surface-container-lowest/80 backdrop-blur-md border-b border-surface-container-high">
        <div className="max-w-7xl mx-auto px-6 md:px-8 h-16 flex items-center justify-between gap-6">
          <div className="flex items-center gap-8">
            <h2 className="text-xl font-extrabold font-headline tracking-tight text-on-surface">
              Strategy Room
            </h2>
            {/* Tab nav */}
            <nav className="flex items-center gap-1">
              {tabs.map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    activeTab === tab.key
                      ? "bg-primary-fixed text-primary"
                      : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low"
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8 py-8">
        {activeTab === "agents" && <AgentsTab />}
        {activeTab === "roadmap" && <RoadmapTab />}
        {activeTab === "market-research" && <MarketResearchTab />}
      </main>
    </div>
  )
}
