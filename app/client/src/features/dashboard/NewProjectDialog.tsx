import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

// Both "Describe your own" and "Help me find one" start a blank project; the
// assistant picks the conversation up from there.
export function NewProjectDialog({
  mode,
  busy,
  onClose,
  onCreate,
}: {
  mode: "describe" | "find" | null
  busy: boolean
  onClose: () => void
  // `firstMessage` is what the assistant is sent as soon as the project opens.
  onCreate: (name: string, firstMessage: string) => void
}) {
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  return (
    <Dialog open={mode !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (name.trim())
              onCreate(
                name.trim(),
                (mode === "describe" && description.trim()) ||
                  "Help me find a decision worth automating",
              )
          }}
          className="space-y-4"
        >
          <DialogHeader>
            <DialogTitle>
              {mode === "find" ? "Help me find one" : "Describe your own"}
            </DialogTitle>
            <DialogDescription>
              {mode === "find"
                ? "Give the project a working name. Your assistant will help you pick a decision to start with."
                : "Give the project a name, then say what the decision is. Your assistant takes it from there."}
            </DialogDescription>
          </DialogHeader>
          <Input
            autoFocus
            value={name}
            maxLength={120}
            placeholder="For example: Refund approvals"
            onChange={(e) => setName(e.target.value)}
          />
          {mode === "describe" && (
            <Textarea
              value={description}
              maxLength={1000}
              placeholder="What decision does your team make again and again? (optional)"
              onChange={(e) => setDescription(e.target.value)}
            />
          )}
          <DialogFooter>
            <Button type="submit" disabled={busy || !name.trim()}>
              Create project
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
