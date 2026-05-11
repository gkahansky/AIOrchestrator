import { useState, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  fetchRoadmap, fetchRoadmapDone, fetchRoadmapFeatures,
  createRoadmapFeature, createRoadmapItem, updateRoadmapItem,
  deleteRoadmapItem, reorderRoadmapItems,
} from "../api"
import {
  RoadmapItem, RoadmapFeature, RoadmapItemType, RoadmapStatus,
} from "../types"

// ── Constants ────────────────────────────────────────────────────────────────

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

type Section = "backlog" | "wip"

// ── ItemRow ──────────────────────────────────────────────────────────────────

interface ItemRowProps {
  item: RoadmapItem
  section: Section
  canDelete: boolean
  onEdit: (item: RoadmapItem) => void
  onDelete: (id: number) => void
  onDragStart: (id: number, section: Section) => void
  onDragOver: (e: React.DragEvent, id: number) => void
  onDrop: (targetSection: Section) => void
  isDragOver: boolean
}

function ItemRow({ item, section, canDelete, onEdit, onDelete, onDragStart, onDragOver, onDrop, isDragOver }: ItemRowProps) {
  return (
    <div
      draggable
      onDragStart={() => onDragStart(item.id, section)}
      onDragOver={e => { e.preventDefault(); onDragOver(e, item.id) }}
      onDrop={e => { e.stopPropagation(); onDrop(section) }}
      className={`flex items-start gap-3 px-4 py-3 bg-surface-container-lowest rounded-xl transition-all cursor-grab active:cursor-grabbing select-none
        ${isDragOver ? "ring-2 ring-primary/40 shadow-float scale-[1.01]" : "shadow-card hover:shadow-float"}`}
    >
      <div className="mt-1 text-on-surface-variant/30 hover:text-on-surface-variant/60 shrink-0" title="Drag to reorder or move">
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

// ── ItemForm ─────────────────────────────────────────────────────────────────

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
          {isNew ? "Add Item" : "Edit Item"}
        </h2>
        <div className="space-y-4">
          {!isNew && (
            <div className="flex items-center gap-2 text-sm text-on-surface-variant">
              <span className="font-medium">ID:</span>
              <span className="font-mono bg-surface-container px-2 py-0.5 rounded-lg text-on-surface-variant">#{item?.id}</span>
            </div>
          )}
          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest font-label opacity-60 mb-1.5">Title *</label>
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
            {isSaving ? "Saving…" : isNew ? "Add Item" : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── RecentlyDoneModal ─────────────────────────────────────────────────────────

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

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Roadmap() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingItem, setEditingItem] = useState<RoadmapItem | null>(null)
  const [showDone, setShowDone] = useState(false)

  // Drag state
  const draggedId = useRef<number | null>(null)
  const draggedSection = useRef<Section | null>(null)
  const dragOverId = useRef<number | null>(null)
  const [dragOverItemId, setDragOverItemId] = useState<number | null>(null)
  const [dragOverSection, setDragOverSection] = useState<Section | null>(null)

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

  function resetDrag() {
    draggedId.current = null
    draggedSection.current = null
    dragOverId.current = null
    setDragOverItemId(null)
    setDragOverSection(null)
  }

  function handleDragStart(id: number, section: Section) {
    draggedId.current = id
    draggedSection.current = section
  }

  function handleItemDragOver(e: React.DragEvent, id: number) {
    e.preventDefault()
    dragOverId.current = id
    setDragOverItemId(id)
  }

  function handleSectionDragOver(e: React.DragEvent, section: Section) {
    e.preventDefault()
    setDragOverSection(section)
  }

  async function handleDrop(targetSection: Section) {
    const fromId = draggedId.current
    const fromSection = draggedSection.current
    const toId = dragOverId.current

    if (fromId === null || fromSection === null) { resetDrag(); return }

    if (fromSection !== targetSection) {
      // Cross-section move — change the item's status to match the target section
      const newStatus: RoadmapStatus = targetSection === "wip" ? "in_progress" : "not_started"
      await updateMutation.mutateAsync({ id: fromId, data: { status: newStatus } })
    } else {
      // Same-section reorder
      if (toId === null || toId === fromId) { resetDrag(); return }
      const list = fromSection === "backlog" ? (roadmap?.backlog ?? []) : (roadmap?.wip ?? [])
      const ids = list.map(i => i.id)
      const fi = ids.indexOf(fromId), ti = ids.indexOf(toId)
      if (fi === -1 || ti === -1) { resetDrag(); return }
      ids.splice(fi, 1)
      ids.splice(ti, 0, fromId)
      reorderMutation.mutate(ids)
    }

    resetDrag()
  }

  function handleSave(data: Parameters<typeof createMutation.mutate>[0]) {
    if (editingItem) updateMutation.mutate({ id: editingItem.id, data })
    else createMutation.mutate(data)
  }

  function handleDelete(id: number) {
    if (!window.confirm("Delete this item?")) return
    deleteMutation.mutate(id)
  }

  async function handleShowDone() { await refetchDone(); setShowDone(true) }

  if (isLoading) return (
    <div className="flex items-center justify-center py-16 text-on-surface-variant text-sm">Loading…</div>
  )

  const backlog = roadmap?.backlog ?? []
  const wip = roadmap?.wip ?? []
  const isDraggingAcross = draggedSection.current !== null

  return (
    <div className="space-y-10">

      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold font-headline text-on-surface tracking-tight mb-1">To Do List</h1>
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
      <section
        className={`bg-surface-container-lowest rounded-2xl shadow-card p-6 transition-all
          ${dragOverSection === "wip" && draggedSection.current === "backlog"
            ? "ring-2 ring-primary/40 shadow-float"
            : ""}`}
        onDragOver={e => handleSectionDragOver(e, "wip")}
        onDragLeave={() => setDragOverSection(null)}
        onDrop={() => handleDrop("wip")}
      >
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>
              trending_up
            </span>
          </div>
          <div>
            <h2 className="text-lg font-bold font-headline text-on-surface">Work in Progress</h2>
            <p className="text-xs text-on-surface-variant">
              {wip.length} active item{wip.length !== 1 ? "s" : ""} · drag to reorder or move to backlog
            </p>
          </div>
        </div>
        {wip.length === 0 ? (
          <div className={`text-on-surface-variant italic text-sm py-10 text-center rounded-xl border-2 border-dashed transition-all
            ${isDraggingAcross && draggedSection.current === "backlog"
              ? "border-primary/40 bg-primary/5 text-primary"
              : "border-outline-variant/40 bg-surface-container-low"}`}>
            {isDraggingAcross && draggedSection.current === "backlog"
              ? "Drop here to move to Work in Progress"
              : "No items in progress."}
          </div>
        ) : (
          <div className="space-y-2">
            {wip.map(item => (
              <ItemRow key={item.id} item={item} section="wip" canDelete={false}
                onEdit={i => { setEditingItem(i); setShowForm(true) }}
                onDelete={handleDelete}
                onDragStart={handleDragStart}
                onDragOver={handleItemDragOver}
                onDrop={handleDrop}
                isDragOver={dragOverItemId === item.id} />
            ))}
          </div>
        )}
      </section>

      {/* Backlog section */}
      <section
        className={`bg-surface-container-lowest rounded-2xl shadow-card p-6 transition-all
          ${dragOverSection === "backlog" && draggedSection.current === "wip"
            ? "ring-2 ring-primary/40 shadow-float"
            : ""}`}
        onDragOver={e => handleSectionDragOver(e, "backlog")}
        onDragLeave={() => setDragOverSection(null)}
        onDrop={() => handleDrop("backlog")}
      >
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-surface-container flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-on-surface-variant" style={{ fontVariationSettings: "'FILL' 1" }}>
              format_list_bulleted
            </span>
          </div>
          <div>
            <h2 className="text-lg font-bold font-headline text-on-surface">Backlog</h2>
            <p className="text-xs text-on-surface-variant">
              {backlog.length} item{backlog.length !== 1 ? "s" : ""} queued · drag to prioritize or move to in progress
            </p>
          </div>
        </div>
        {backlog.length === 0 ? (
          <div className={`text-on-surface-variant italic text-sm py-10 text-center rounded-xl border-2 border-dashed transition-all
            ${isDraggingAcross && draggedSection.current === "wip"
              ? "border-primary/40 bg-primary/5 text-primary"
              : "border-outline-variant/40 bg-surface-container-low"}`}>
            {isDraggingAcross && draggedSection.current === "wip"
              ? "Drop here to move back to Backlog"
              : "No backlog items yet. Click \"+ Add Item\" to get started."}
          </div>
        ) : (
          <div className="space-y-2">
            {backlog.map(item => (
              <ItemRow key={item.id} item={item} section="backlog" canDelete
                onEdit={i => { setEditingItem(i); setShowForm(true) }}
                onDelete={handleDelete}
                onDragStart={handleDragStart}
                onDragOver={handleItemDragOver}
                onDrop={handleDrop}
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
