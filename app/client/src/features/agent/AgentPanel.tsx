import { useEffect, useRef } from "react"
import { useLocation, useNavigate } from "react-router"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { Project } from "@/lib/api/types"
import { Composer } from "./Composer"
import { MessageList } from "./MessageList"
import { useAgent, type CanvasEvent } from "./useAgent"

const STARTERS = ["Look over my rules", "Try it on an example", "Add a rule"]

export function AgentPanel({
  project,
  stage,
  onCanvas,
  onStage,
}: {
  project: Project
  stage: string
  onCanvas: (e: CanvasEvent) => void
  onStage: (stage: string) => void
}) {
  const { events, loaded, loadError, reload, busy, send } = useAgent(
    project.id,
    {
      onCanvas,
      onStage,
    },
    stage,
  )
  const location = useLocation()
  const navigate = useNavigate()
  const firstMessage = (location.state as { firstMessage?: string } | null)
    ?.firstMessage
  const sentFirst = useRef(false)

  // The dashboard hands a new blank project its opening message; send it once
  // and drop it from history state so a reload doesn't repeat it.
  useEffect(() => {
    if (!loaded || !firstMessage || sentFirst.current) return
    sentFirst.current = true
    navigate(location.pathname, { replace: true, state: null })
    if (events.length === 0) void send(firstMessage)
  }, [loaded, firstMessage, events.length, send, navigate, location.pathname])

  const empty = loaded && !loadError && events.length === 0 && !firstMessage

  return (
    <Card className="flex h-[70vh] flex-col lg:h-[calc(100vh-14rem)]">
      <CardHeader>
        <CardTitle>Assistant</CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
        {empty && !busy && (
          <div className="space-y-2">
            <p className="text-sm">
              {project.template_id
                ? `I've loaded ${project.name} with its rules. Want me to look it over, or try it on a few examples?`
                : "Tell me about a decision your team makes again and again, or ask me to help you find one."}
            </p>
            {project.template_id && (
              <div className="flex flex-wrap gap-2">
                {STARTERS.map((s) => (
                  <Button
                    key={s}
                    size="sm"
                    variant="outline"
                    onClick={() => void send(s)}
                  >
                    {s}
                  </Button>
                ))}
              </div>
            )}
          </div>
        )}
        {loadError && (
          <div className="space-y-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm">
            <p className="text-destructive">Couldn't load the conversation.</p>
            <Button size="sm" variant="outline" onClick={reload}>
              Retry
            </Button>
          </div>
        )}
        <MessageList
          events={events}
          projectId={project.id}
          busy={busy}
          onSend={(t) => void send(t)}
          onRetry={(t) => void send(t, false)}
        />
        <Composer busy={busy || !loaded} onSend={(t) => void send(t)} />
      </CardContent>
    </Card>
  )
}
