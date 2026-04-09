import { useState, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  fetchProposals, approveProposal, rejectProposal,
  fetchAdvisors, updateAdvisorPrompt,
  fetchRoadmap, fetchRoadmapDone, fetchRoadmapFeatures,
  createRoadmapFeature, createRoadmapItem, updateRoadmapItem,
  deleteRoadmapItem, reorderRoadmapItems,
} from "../api"
import type {
  AdvisorConfig,
  RoadmapItem,
  RoadmapFeature,
  RoadmapItemType,
  RoadmapStatus,
} from "../types"

// ── Helpers ───────────────────────────────────────────────────────────────────

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

// ── Item Form Modal ───────────────────────────────────────────────────────────

interface ItemFormProps {
  item: Partial<RoadmapItem> | null   // null = new item
  features: RoadmapFeature[]
  onSave: (data: {
    title: string
    description: string
    item_type: RoadmapItemType
    feature_id: number | null
    status: RoadmapStatus
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
    if (val === "__add__") {
      setAddingFeature(true)
      return
    }
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

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-5">
          {isNew ? "Add Backlog Item" : "Edit Item"}
        </h2>

        <div className="space-y-4">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Title <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              maxLength={100}
              value={title}
              onChange={e => setTitle(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Short title (max 100 chars)"
            />
            <p className="text-xs text-gray-400 mt-1">{title.length}/100</p>
          </div>

          {/* Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select
              value={itemType}
              onChange={e => setItemType(e.target.value as RoadmapItemType)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
            >
              {ITEM_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          {/* Feature */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Feature</label>
            {addingFeature ? (
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newFeatureName}
                  onChange={e => setNewFeatureName(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && confirmNewFeature()}
                  className="flex-1 border border-blue-400 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
                  placeholder="New feature name"
                  autoFocus
                />
                <button
                  onClick={confirmNewFeature}
                  className="px-3 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
                >
                  Add
                </button>
                <button
                  onClick={() => { setAddingFeature(false); setNewFeatureName("") }}
                  className="px-3 py-2 border border-gray-300 text-gray-700 text-sm rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <select
                value={featureId ?? ""}
                onChange={e => handleFeatureChange(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
              >
                <option value="">— None —</option>
                {features.map(f => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
                <option value="__add__">+ Add feature…</option>
              </select>
            )}
            {featureError && <p className="text-xs text-red-500 mt-1">{featureError}</p>}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              maxLength={500}
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={3}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 resize-none"
              placeholder="Optional description (max 500 chars)"
            />
            <p className="text-xs text-gray-400 mt-1">{description.length}/500</p>
          </div>

          {/* Status — only shown when editing */}
          {!isNew && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select
                value={status}
                onChange={e => setStatus(e.target.value as RoadmapStatus)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
              >
                {ALL_STATUSES.map(s => (
                  <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-gray-100">
          <button
            onClick={onCancel}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md text-sm hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSaving || !title.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {isSaving ? "Saving…" : isNew ? "Add to Backlog" : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Recently Done Modal ───────────────────────────────────────────────────────

function RecentlyDoneModal({ items, onClose }: { items: RoadmapItem[]; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-xl mx-4 p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Recently Done (last 30 days)</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>
        {items.length === 0 ? (
          <p className="text-gray-500 italic py-4 text-center">No items completed in the last 30 days.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left py-2 pr-4 text-gray-500 font-medium w-12">#</th>
                <th className="text-left py-2 pr-4 text-gray-500 font-medium">Title</th>
                <th className="text-left py-2 text-gray-500 font-medium">Completed</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id} className="border-b border-gray-50">
                  <td className="py-2 pr-4 text-gray-400">{item.id}</td>
                  <td className="py-2 pr-4 text-gray-800">{item.title}</td>
                  <td className="py-2 text-gray-500">
                    {item.completed_at
                      ? new Date(item.completed_at).toLocaleDateString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="flex justify-end mt-4">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md text-sm hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Draggable Item Row ────────────────────────────────────────────────────────

interface ItemRowProps {
  item: RoadmapItem
  canDelete: boolean
  onEdit: (item: RoadmapItem) => void
  onDelete: (id: number) => void
  onDragStart: (id: number) => void
  onDragOver: (e: React.DragEvent, id: number) => void
  onDrop: () => void
  isDragOver: boolean
}

function ItemRow({ item, canDelete, onEdit, onDelete, onDragStart, onDragOver, onDrop, isDragOver }: ItemRowProps) {
  return (
    <div
      draggable
      onDragStart={() => onDragStart(item.id)}
      onDragOver={e => { e.preventDefault(); onDragOver(e, item.id) }}
      onDrop={onDrop}
      className={`flex items-start gap-3 p-3 bg-white rounded-lg border transition-all cursor-grab active:cursor-grabbing select-none
        ${isDragOver ? "border-blue-400 shadow-md bg-blue-50" : "border-gray-200 hover:border-gray-300 hover:shadow-sm"}`}
    >
      {/* Drag handle */}
      <div className="mt-1 text-gray-300 hover:text-gray-500 shrink-0" title="Drag to reorder">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
          <circle cx="4" cy="3" r="1.2"/><circle cx="10" cy="3" r="1.2"/>
          <circle cx="4" cy="7" r="1.2"/><circle cx="10" cy="7" r="1.2"/>
          <circle cx="4" cy="11" r="1.2"/><circle cx="10" cy="11" r="1.2"/>
        </svg>
      </div>

      {/* ID */}
      <span className="text-xs text-gray-400 mt-0.5 shrink-0 w-8">#{item.id}</span>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <span className="font-medium text-gray-800 text-sm truncate">{item.title}</span>
          {item.item_type && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_COLOURS[item.item_type] ?? "bg-gray-100 text-gray-600"}`}>
              {item.item_type}
            </span>
          )}
          {item.feature_name && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
              {item.feature_name}
            </span>
          )}
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOURS[item.status] ?? "bg-gray-100 text-gray-500"}`}>
            {STATUS_LABELS[item.status]}
          </span>
        </div>
        {item.description && (
          <p className="text-xs text-gray-500 line-clamp-2">{item.description}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-1 shrink-0">
        <button
          onClick={() => onEdit(item)}
          className="text-xs px-2 py-1 border border-gray-200 rounded text-gray-600 hover:bg-gray-50"
        >
          Edit
        </button>
        {canDelete && (
          <button
            onClick={() => onDelete(item.id)}
            className="text-xs px-2 py-1 border border-red-200 rounded text-red-600 hover:bg-red-50"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  )
}

// ── Roadmap Tab ───────────────────────────────────────────────────────────────

function RoadmapTab() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState<RoadmapItem | null>(null)
  const [showDone, setShowDone] = useState(false)
  const draggedId = useRef<number | null>(null)
  const dragOverId = useRef<number | null>(null)
  const [dragOverItemId, setDragOverItemId] = useState<number | null>(null)

  const { data: roadmap, isLoading } = useQuery({
    queryKey: ["roadmap"],
    queryFn: fetchRoadmap,
  })
  const { data: features = [] } = useQuery({
    queryKey: ["roadmap_features"],
    queryFn: fetchRoadmapFeatures,
  })
  const { data: doneItems = [], refetch: refetchDone } = useQuery({
    queryKey: ["roadmap_done"],
    queryFn: fetchRoadmapDone,
    enabled: false,
  })

  const createFeatureMutation = useMutation({
    mutationFn: (name: string) => createRoadmapFeature(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["roadmap_features"] }),
  })

  const createMutation = useMutation({
    mutationFn: createRoadmapItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roadmap"] })
      setShowForm(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof updateRoadmapItem>[1] }) =>
      updateRoadmapItem(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roadmap"] })
      setEditingItem(null)
    },
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
    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  function openEdit(item: RoadmapItem) {
    setEditingItem(item)
    setShowForm(true)
  }

  function handleDelete(id: number) {
    if (!window.confirm("Delete this item?")) return
    deleteMutation.mutate(id)
  }

  function handleDragStart(id: number) {
    draggedId.current = id
  }

  function handleDragOver(e: React.DragEvent, id: number) {
    e.preventDefault()
    dragOverId.current = id
    setDragOverItemId(id)
  }

  function handleDrop(section: "backlog" | "wip") {
    const from = draggedId.current
    const to = dragOverId.current
    if (from === null || to === null || from === to) {
      draggedId.current = null
      dragOverId.current = null
      setDragOverItemId(null)
      return
    }
    const list = section === "backlog" ? (roadmap?.backlog ?? []) : (roadmap?.wip ?? [])
    const ids = list.map(i => i.id)
    const fromIdx = ids.indexOf(from)
    const toIdx = ids.indexOf(to)
    if (fromIdx === -1 || toIdx === -1) return
    ids.splice(fromIdx, 1)
    ids.splice(toIdx, 0, from)
    reorderMutation.mutate(ids)
    draggedId.current = null
    dragOverId.current = null
    setDragOverItemId(null)
  }

  async function handleShowDone() {
    await refetchDone()
    setShowDone(true)
  }

  if (isLoading) return <div className="text-gray-500 py-8 text-center">Loading roadmap…</div>

  const backlog = roadmap?.backlog ?? []
  const wip = roadmap?.wip ?? []

  return (
    <div className="space-y-8">
      {/* Controls */}
      <div className="flex justify-between items-center">
        <div className="flex gap-3">
          <button
            onClick={() => { setEditingItem(null); setShowForm(true) }}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
          >
            + Add Item
          </button>
          <button
            onClick={handleShowDone}
            className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50"
          >
            Recently Done
          </button>
        </div>
        <p className="text-xs text-gray-400">{backlog.length} in backlog · {wip.length} in progress</p>
      </div>

      {/* Product Backlog */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-gray-400 inline-block"></span>
          Product Backlog
          <span className="text-xs text-gray-400 font-normal ml-1">({backlog.length})</span>
        </h2>
        {backlog.length === 0 ? (
          <div className="text-gray-400 italic text-sm py-6 text-center border border-dashed border-gray-200 rounded-lg">
            No backlog items. Click "+ Add Item" to start.
          </div>
        ) : (
          <div className="space-y-2">
            {backlog.map(item => (
              <ItemRow
                key={item.id}
                item={item}
                canDelete
                onEdit={openEdit}
                onDelete={handleDelete}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDrop={() => handleDrop("backlog")}
                isDragOver={dragOverItemId === item.id}
              />
            ))}
          </div>
        )}
      </section>

      {/* Work in Progress */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block"></span>
          Work in Progress
          <span className="text-xs text-gray-400 font-normal ml-1">({wip.length})</span>
        </h2>
        {wip.length === 0 ? (
          <div className="text-gray-400 italic text-sm py-6 text-center border border-dashed border-gray-200 rounded-lg">
            No items in progress.
          </div>
        ) : (
          <div className="space-y-2">
            {wip.map(item => (
              <ItemRow
                key={item.id}
                item={item}
                canDelete={false}
                onEdit={openEdit}
                onDelete={handleDelete}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDrop={() => handleDrop("wip")}
                isDragOver={dragOverItemId === item.id}
              />
            ))}
          </div>
        )}
      </section>

      {/* Item form modal */}
      {showForm && (
        <ItemForm
          item={editingItem}
          features={features}
          onSave={handleSave}
          onCancel={() => { setShowForm(false); setEditingItem(null) }}
          onAddFeature={name => createFeatureMutation.mutateAsync(name)}
          isSaving={createMutation.isPending || updateMutation.isPending}
        />
      )}

      {/* Recently Done modal */}
      {showDone && (
        <RecentlyDoneModal items={doneItems} onClose={() => setShowDone(false)} />
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function StrategyRoom() {
  const [activeTab, setActiveTab] = useState<"proposals" | "prompts" | "roadmap">("proposals")
  const [editingPromptId, setEditingPromptId] = useState<string | null>(null)
  const [promptText, setPromptText] = useState("")

  const queryClient = useQueryClient()
  const { data: proposals = [], isLoading: loadingProposals, error: proposalError } = useQuery({
    queryKey: ["strategy_proposals"],
    queryFn: fetchProposals,
    refetchInterval: 30_000,
  })

  const { data: advisors = [], isLoading: loadingAdvisors, error: advisorError } = useQuery({
    queryKey: ["strategy_advisors"],
    queryFn: fetchAdvisors,
    staleTime: 5 * 60_000,
  })

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

  const savePromptMutation = useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) => updateAdvisorPrompt(id, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategy_advisors"] })
      setEditingPromptId(null)
    },
  })

  if (loadingProposals || loadingAdvisors) return <div className="p-6">Loading data...</div>
  if (proposalError || advisorError) return <div className="p-6 text-red-500">Error loading data</div>

  const tabs: { key: "proposals" | "prompts" | "roadmap"; label: string }[] = [
    { key: "proposals", label: "Pending Proposals" },
    { key: "roadmap", label: "Roadmap" },
    { key: "prompts", label: "System Prompts" },
  ]

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6 flex justify-between items-end border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Strategy Room</h1>
          <p className="text-gray-500">AI advisory ecosystem control center.</p>
        </div>
        <div className="flex rounded-md shadow-sm" role="group">
          {tabs.map((tab, i) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-medium border border-gray-200
                ${i === 0 ? "rounded-l-lg" : ""}
                ${i === tabs.length - 1 ? "rounded-r-lg" : "border-r-0"}
                ${activeTab === tab.key
                  ? "bg-white text-blue-700"
                  : "bg-gray-50 text-gray-900 hover:bg-gray-100 focus:z-10 focus:ring-2 focus:ring-blue-700"
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "proposals" && (
        <div className="grid gap-6 grid-cols-1 md:grid-cols-2">
          {proposals.length === 0 ? (
            <div className="text-gray-500 italic p-6 bg-white rounded-lg border border-gray-200">
              No pending proposals. You're all caught up!
            </div>
          ) : (
            proposals.map(proposal => (
              <div key={proposal.id} className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
                <div className="flex justify-between items-start mb-4">
                  <div className="flex flex-col">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      {proposal.advisor_id.toUpperCase()}
                    </span>
                    <h3 className="mt-2 text-lg font-medium text-gray-900">{proposal.category}</h3>
                  </div>
                  <span className="text-sm text-gray-500">Priority: {proposal.priority}</span>
                </div>

                <div className="prose prose-sm text-gray-600 mb-6 bg-gray-50 p-4 rounded-md h-48 overflow-y-auto w-full">
                  <pre className="whitespace-pre-wrap font-sans">{proposal.content}</pre>
                </div>

                <div className="flex gap-3 justify-end border-t border-gray-100 pt-4">
                  <button
                    onClick={() => rejectMutation.mutate(proposal.id)}
                    disabled={rejectMutation.isPending}
                    className="px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-red-700 bg-white hover:bg-gray-50"
                  >
                    {rejectMutation.isPending ? "Rejecting..." : "Reject"}
                  </button>
                  <button
                    onClick={() => approveMutation.mutate(proposal.id)}
                    disabled={approveMutation.isPending}
                    className="px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700"
                  >
                    {approveMutation.isPending ? "Approving..." : "Approve to Roadmap"}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === "roadmap" && <RoadmapTab />}

      {activeTab === "prompts" && (
        <div className="grid gap-6 grid-cols-1">
          {advisors.map((adv: AdvisorConfig) => (
            <div key={adv.id} className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold text-gray-900 capitalize">{adv.id}</h3>
                <div className="text-sm space-x-2">
                  <span className="bg-purple-100 text-purple-800 px-2 py-1 rounded">{adv.model}</span>
                </div>
              </div>

              <div className="mb-4">
                <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-2">Capabilities</h4>
                <div className="flex flex-wrap gap-2">
                  {adv.capabilities.map(cap => (
                    <span key={cap} className="bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs">
                      {cap}
                    </span>
                  ))}
                </div>
              </div>

              <div className="mt-4">
                <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-2">
                  System Prompt ({adv.prompt_ref}.md)
                </h4>
                {editingPromptId === adv.id ? (
                  <div className="space-y-3">
                    <textarea
                      value={promptText}
                      onChange={e => setPromptText(e.target.value)}
                      className="w-full h-64 p-3 border border-blue-300 rounded font-mono text-sm leading-relaxed focus:ring-blue-500 focus:border-blue-500"
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setEditingPromptId(null)}
                        className="px-3 py-1.5 border border-gray-300 text-gray-700 rounded hover:bg-gray-50 text-sm font-medium"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => savePromptMutation.mutate({ id: adv.id, content: promptText })}
                        disabled={savePromptMutation.isPending}
                        className="px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium"
                      >
                        {savePromptMutation.isPending ? "Saving..." : "Save Changes"}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="relative group">
                    <pre className="whitespace-pre-wrap font-sans text-sm text-gray-600 bg-gray-50 p-4 rounded border border-gray-100 max-h-96 overflow-y-auto">
                      {adv.system_prompt}
                    </pre>
                    <button
                      onClick={() => {
                        setEditingPromptId(adv.id)
                        setPromptText(adv.system_prompt)
                      }}
                      className="absolute top-2 right-2 bg-white border border-gray-300 text-gray-700 px-3 py-1 rounded text-xs font-medium opacity-0 group-hover:opacity-100 transition-opacity hover:bg-gray-50 shadow-sm"
                    >
                      Edit Prompt
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
