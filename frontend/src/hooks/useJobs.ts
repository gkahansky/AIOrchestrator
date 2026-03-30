import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { fetchJobs, fetchJob, approveJob, rejectJob, retryJob } from "../api"

export function useJobs(params?: { venture?: string; status?: string; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () => fetchJobs(params),
    refetchInterval: 30_000,
    retry: 2,
  })
}

export function useJob(id: string) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: () => fetchJob(id),
    refetchInterval: 15_000,
    retry: 2,
    enabled: !!id,
  })
}

export function useApproveJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) => approveJob(id, notes),
    onSuccess: (_data, { id }) => {
      void qc.invalidateQueries({ queryKey: ["job", id] })
      void qc.invalidateQueries({ queryKey: ["jobs"] })
      void qc.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}

export function useRejectJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) => rejectJob(id, notes),
    onSuccess: (_data, { id }) => {
      void qc.invalidateQueries({ queryKey: ["job", id] })
      void qc.invalidateQueries({ queryKey: ["jobs"] })
      void qc.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}

export function useRetryJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: string }) => retryJob(id),
    onSuccess: (_data, { id }) => {
      void qc.invalidateQueries({ queryKey: ["job", id] })
      void qc.invalidateQueries({ queryKey: ["jobs"] })
      void qc.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })
}
