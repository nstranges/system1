import { useAuth } from "@clerk/react"
import { useCallback, useEffect, useRef, useState } from "react"
import { useApi } from "@/lib/api/client"
import { SseError, streamEvents } from "@/lib/sse"
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

function failureText(err: unknown): string {
  if (err instanceof SseError) {
    if (err.status === 429)
      return "You're sending messages too fast. Wait a moment."
    if (err.status === 404) return "This project couldn't be found."
    if (err.serverMessage) return err.serverMessage
  }
  return "We lost the connection to your assistant."
}

export function useAgent(projectId: string, handlers: Handlers) {
  const api = useApi()
  const { getToken } = useAuth()
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const abort = useRef<AbortController | null>(null)
  // Handlers change every render; the stream callback reads the latest ones.
  const latest = useRef(handlers)
  useEffect(() => {
    latest.current = handlers
  })

  // Reset and abort on a project change only. An `api` identity change must
  // not cut a running stream, so this is separate from the history load.
  useEffect(() => {
    setEvents([])
    setLoaded(false)
    setLoadError(false)
    setBusy(false)
    return () => {
      abort.current?.abort()
      abort.current = null
    }
  }, [projectId])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const { data } = await api.GET(
          "/api/projects/{project_id}/agent/history",
          { params: { path: { project_id: projectId } } },
        )
        if (cancelled) return
        if (!data) throw new Error("no history")
        setEvents(data.reduce<AgentEvent[]>(append, []))
        setLoadError(false)
        setLoaded(true)
      } catch {
        if (!cancelled) setLoadError(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [api, projectId, reloadKey])

  const reload = useCallback(() => {
    setLoadError(false)
    setReloadKey((k) => k + 1)
  }, [])

  // `echo` is false when retrying, so the user's bubble isn't duplicated.
  const send = useCallback(
    async (text: string, echo = true) => {
      const trimmed = text.trim()
      if (!trimmed || abort.current) return
      const controller = new AbortController()
      abort.current = controller
      setBusy(true)
      if (echo) setEvents((es) => append(es, { type: "user", text: trimmed }))
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
      } catch (err) {
        if (!controller.signal.aborted) {
          setEvents((es) =>
            append(es, { type: "error", message: failureText(err) }),
          )
        }
      } finally {
        // Only the stream that is still current owns `busy`; a project change
        // has already reset it and may have started its own stream.
        if (abort.current === controller) {
          abort.current = null
          setBusy(false)
        }
      }
    },
    [getToken, projectId],
  )

  return { events, loaded, loadError, reload, busy, send }
}
