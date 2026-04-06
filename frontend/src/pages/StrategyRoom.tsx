import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { fetchProposals, approveProposal, rejectProposal, fetchAdvisors, updateAdvisorPrompt } from "../api"
import type { AdvisorConfig } from "../types"

export default function StrategyRoom() {
  const [activeTab, setActiveTab] = useState<"proposals" | "prompts">("proposals")
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
    }
  })

  const rejectMutation = useMutation({
    mutationFn: rejectProposal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategy_proposals"] })
    }
  })

  const savePromptMutation = useMutation({
    mutationFn: ({ id, content }: { id: string, content: string }) => updateAdvisorPrompt(id, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategy_advisors"] })
      setEditingPromptId(null)
    }
  })

  if (loadingProposals || loadingAdvisors) return <div className="p-6">Loading data...</div>
  if (proposalError || advisorError) return <div className="p-6 text-red-500">Error loading data</div>

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6 flex justify-between items-end border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Strategy Room</h1>
          <p className="text-gray-500">AI advisory ecosystem control center.</p>
        </div>
        <div className="flex rounded-md shadow-sm" role="group">
          <button
            onClick={() => setActiveTab("proposals")}
            className={`px-4 py-2 text-sm font-medium rounded-l-lg border border-gray-200 ${
              activeTab === "proposals" ? "bg-white text-blue-700" : "bg-gray-50 text-gray-900 hover:bg-gray-100 focus:z-10 focus:ring-2 focus:ring-blue-700"
            }`}
          >
            Pending Proposals
          </button>
          <button
            onClick={() => setActiveTab("prompts")}
            className={`px-4 py-2 text-sm font-medium rounded-r-lg border border-gray-200 border-l-0 ${
              activeTab === "prompts" ? "bg-white text-blue-700" : "bg-gray-50 text-gray-900 hover:bg-gray-100 focus:z-10 focus:ring-2 focus:ring-blue-700"
            }`}
          >
            System Prompts
          </button>
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
                  className="px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-red-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                >
                  {rejectMutation.isPending ? "Rejecting..." : "Reject"}
                </button>
                
                <button
                  onClick={() => approveMutation.mutate(proposal.id)}
                  disabled={approveMutation.isPending}
                  className="px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                >
                  {approveMutation.isPending ? "Approving..." : "Approve to Roadmap"}
                </button>
              </div>
            </div>
          ))
        )}
        </div>
      )}

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
                      onChange={(e) => setPromptText(e.target.value)}
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
