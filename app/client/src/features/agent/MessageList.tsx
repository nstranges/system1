import { useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { CanvasChangeCard } from "./cards/CanvasChangeCard"
import { ChoicesCard } from "./cards/ChoicesCard"
import { ConfirmCard } from "./cards/ConfirmCard"
import { FitCard } from "./cards/FitCard"
import { TryResultCard } from "./cards/TryResultCard"
import type { AgentEvent } from "./useAgent"

// Tool summaries are the model's own words, so only errors show them; the
// rest get a fixed plain-words line when the tool starts.
const TOOL_WORDS: Record<string, string> = {
  search_use_cases: "Looking through example decisions…",
  set_inputs: "Updating what your decision looks at…",
  set_options: "Updating the possible answers…",
  set_rules: "Updating your rules…",
  try_decision: "Trying it on an example…",
  request_dataset: "Preparing the examples plan…",
  request_training: "Preparing the training plan…",
}

function toolLine(name: string, status: string, summary: string) {
  if (status === "error") return summary || "That step didn't work."
  return TOOL_WORDS[name] ?? "Working on it…"
}

export function MessageList({
  events,
  projectId,
  busy,
  onSend,
  onRetry,
}: {
  events: AgentEvent[]
  projectId: string
  busy: boolean
  onSend: (text: string) => void
  onRetry: (text: string) => void
}) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" })
  }, [events])

  // Choices count as answered once the user speaks again.
  // The server ends every turn with `done`, so "last" skips the quiet events.
  let lastShown = -1
  let lastChoices = -1
  let lastUser = -1
  let lastUserText = ""
  events.forEach((e, i) => {
    if (e.type !== "done" && e.type !== "stage") lastShown = i
    if (e.type === "choices") lastChoices = i
    if (e.type === "user") {
      lastUser = i
      lastUserText = e.text
    }
  })

  return (
    <div className="flex-1 space-y-3 overflow-y-auto pr-1" aria-live="polite">
      {events.map((e, i) => {
        switch (e.type) {
          case "user":
            return (
              <div key={i} className="flex justify-end">
                <p className="max-w-[85%] rounded-2xl bg-primary px-3 py-2 text-sm whitespace-pre-wrap text-primary-foreground">
                  {e.text}
                </p>
              </div>
            )
          case "text":
            return (
              <p key={i} className="text-sm whitespace-pre-wrap">
                {e.delta}
              </p>
            )
          case "tool":
            if (
              e.status === "done" ||
              e.name === "show_choices" ||
              e.name === "show_fit" ||
              e.name === "go_to_stage"
            ) {
              if (e.status !== "error") return null
            }
            if (
              e.status === "started" &&
              events[i + 1]?.type === "tool" &&
              (events[i + 1] as { status: string }).status === "error" &&
              (events[i + 1] as { name: string }).name === e.name
            )
              return null
            return (
              <p
                key={i}
                className={cn(
                  "text-xs",
                  e.status === "error"
                    ? "text-destructive"
                    : "text-muted-foreground",
                )}
              >
                {toolLine(e.name, e.status, e.summary)}
              </p>
            )
          case "choices":
            return (
              <ChoicesCard
                key={i}
                question={e.question}
                options={e.options}
                active={i === lastChoices && i > lastUser && !busy}
                onPick={onSend}
              />
            )
          case "fit":
            return <FitCard key={i} event={e} />
          case "canvas":
            return <CanvasChangeCard key={i} event={e} projectId={projectId} />
          case "try_result":
            return <TryResultCard key={i} event={e} />
          case "confirm":
            return <ConfirmCard key={i} event={e} projectId={projectId} />
          case "error":
            return (
              <div
                key={i}
                className="space-y-1.5 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm"
              >
                <p className="text-destructive">{e.message}</p>
                {i === lastShown && lastUserText && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => onRetry(lastUserText)}
                  >
                    Try again
                  </Button>
                )}
              </div>
            )
          default:
            // stage and done only drive behaviour; nothing to show.
            return null
        }
      })}
      {busy && <p className="text-xs text-muted-foreground">Thinking…</p>}
      <div ref={end} />
    </div>
  )
}
