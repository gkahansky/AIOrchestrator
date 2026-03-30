import { useQuery } from "@tanstack/react-query"
import { fetchFinance } from "../api"

export function useFinance() {
  return useQuery({
    queryKey: ["finance"],
    queryFn: fetchFinance,
    refetchInterval: 60_000,
    retry: 2,
  })
}
