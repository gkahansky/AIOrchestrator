import { useParams } from "react-router-dom"
import { MarketResearchTab } from "./StrategyRoom"

export default function MarketResearch() {
  const { sessionId } = useParams<{ sessionId?: string }>()
  return <MarketResearchTab initialSessionId={sessionId ?? null} />
}
