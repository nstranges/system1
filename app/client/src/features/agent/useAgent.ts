import { useAuth } from "@clerk/react"
import { useCallback, useEffect, useRef, useState } from "react"
import { useApi } from "@/lib/api/client"
import { streamEvents } from "@/lib/sse"
import type { components } from "@/lib/api/schema"

export type AgentEvent =
  | components["schemas"]["UserEvent"]
  | components["schemas"]["TextEvent"]
  | components["schemas"]["ToolEvent"]
  | components["schemas"]["ChoicesEvent"]
  | components["schemas"]["FitEvent"]
  | components["schemas"]["CanvasEvent"]
  | components["schemas"]["TryResultEvent"]
  | components["schemas"]["ConfirmEvent"]
  | components["schemas"]["StageEvent"]
  | components["schemas"]["ErrorEvent"]
  | components["schemas"]["DoneEvent"]

export type CanvasEvent = components["schemas"]["CanvasEvent"]

interface Handlers {
  onCanvas: (e: CanvasEvent) => void
  onStage: (stage: string) => void
}

// Consecutive text deltas become one assistant message.
function append(events: AgentEvent[], e: AgentEvent): AgentEvent[] {
  const last = events[events.length - 1]
  if (e.type === "text" && last?.type === "text") {
    return [...events.slice(0, -1), { ...last, delta: last.delta + e.delta }]
  }
  return [...events, e]
}

export function useAgent(projectId: string, handlers: Handlers) {
  const api = useApi()
  const { getToken } = useAuth()
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const abort = useRef<AbortController | null>(null)
  // Handlers change every render; the stream callback reads the latest ones.
  const latest = useRef(handlers)
  useEffect(() => {
    latest.current = handlers
  })

  useEffect(() => {
    let cancelled = false
    void (async () => {
      let history: AgentEvent[] = []
      try {
        const { data } = await api.GET(
          "/api/projects/{project_id}/agent/history",
          { params: { path: { project_id: projectId } } },
        )
        history = (data ?? []).reduce<AgentEvent[]>(append, [])
      } catch {
        // An unreadable history just means starting with a clean panel.
      }
      if (cancelled) return
      setEvents(history)
      setLoaded(true)
    })()
    return () => {
      cancelled = true
      abort.current?.abort()
    }
  }, [api, projectId])

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || abort.current) return
      const controller = new AbortController()
      abort.current = controller
      setBusy(true)
      setEvents((es) => append(es, { type: "user", text: trimmed }))
      try {
        const token = await getToken()
        if (!token) throw new Error("signed out")
        await streamEvents(
          `/api/projects/${projectId}/agent/messages`,
          { text: trimmed },
          token,
          ({ data }) => {
            const e = data as AgentEvent
            if (!e || typeof e !== "object" || !("type" in e)) return
            setEvents((es) => append(es, e))
            if (e.type === "canvas") latest.current.onCanvas(e)
            else if (e.type === "stage") latest.current.onStage(e.stage)
          },
          controller.signal,
        )
      } catch {
        if (!controller.signal.aborted) {
          setEvents((es) =>
            append(es, {
              type: "error",
              message: "We lost the connection to your assistant.",
            }),
          )
        }
      } finally {
        if (abort.current === controller) abort.current = null
        if (!controller.signal.aborted) setBusy(false)
      }
    },
    [getToken, projectId],
  )

  return { events, loaded, busy, send }
}
