import { SendHorizontal } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

const LIMIT = 2000
const WARN_AT = 1800

export function Composer({
  busy,
  onSend,
}: {
  busy: boolean
  onSend: (text: string) => void
}) {
  const [text, setText] = useState("")
  const tooLong = text.length > LIMIT

  function submit() {
    if (busy || tooLong || !text.trim()) return
    onSend(text)
    setText("")
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-end gap-2">
        <Textarea
          value={text}
          disabled={busy}
          rows={2}
          className="max-h-40 min-h-10 resize-none"
          placeholder={busy ? "Working on it…" : "Ask or tell your assistant"}
          aria-label="Message your assistant"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault()
              submit()
            }
          }}
        />
        <Button
          size="icon"
          aria-label="Send"
          disabled={busy || tooLong || !text.trim()}
          onClick={submit}
        >
          <SendHorizontal />
        </Button>
      </div>
      {text.length >= WARN_AT && (
        <p
          className={
            tooLong
              ? "text-xs text-destructive"
              : "text-xs text-muted-foreground"
          }
        >
          {tooLong
            ? `Too long by ${text.length - LIMIT} characters. Try a shorter message.`
            : `Keep it short: ${LIMIT - text.length} characters left.`}
        </p>
      )}
    </div>
  )
}
