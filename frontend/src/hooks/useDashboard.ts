import { useQuery } from "@tanstack/react-query"
import { fetchDashboard } from "../api"

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
    refetchInterval: 30_000,
    retry: 2,
  })
}
