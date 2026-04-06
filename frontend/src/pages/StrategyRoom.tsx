import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { fetchProposals, approveProposal, rejectProposal } from "../../api"

export default function StrategyRoom() {
  const queryClient = useQueryClient()
  const { data: proposals = [], isLoading, error } = useQuery({
    queryKey: ["strategy_proposals"],
    queryFn: fetchProposals,
    refetchInterval: 30_000,
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

  if (isLoading) return <div className="p-6">Loading proposals...</div>
  if (error) return <div className="p-6 text-red-500">Error loading proposals</div>

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Strategy Room</h1>
        <p className="text-gray-500">AI-generated advisory proposals awaiting review.</p>
      </div>

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
    </div>
  )
}
