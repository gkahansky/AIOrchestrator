import { useQuery } from "@tanstack/react-query"
import { fetchHealth } from "../api"

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    retry: 2,
  })
}
