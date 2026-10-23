import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
import type { Template } from "@/lib/api/types"
import { TemplateCard } from "./TemplateCard"

export type StartMode = "scratch" | "upload" | "documents"

const STARTS: { mode: StartMode | "example"; title: string; text: string }[] = [
  {
    mode: "scratch",
    title: "From scratch",
    text: "Your assistant helps you describe the decision.",
  },
  {
    mode: "example",
    title: "From an example",
    text: "Start from a ready-made decision and change it.",
  },
  {
    mode: "upload",
    title: "From my past decisions",
    text: "Upload a file of decisions you've already made.",
  },
  {
    mode: "documents",
    title: "From my documents",
    text: "Share a policy or guide and we'll read it.",
  },
]

export function NewProjectDialog({
  open,
  templates,
  busy,
  onClose,
  onStart,
  onTemplate,
}: {
  open: boolean
  templates: Template[] | null
  busy: boolean
  onClose: () => void
  onStart: (mode: StartMode, name: string, deciding: string) => void
  onTemplate: (template: Template, name: string) => void
}) {
  const [step, setStep] = useState<"name" | "start" | "examples">("name")
  const [name, setName] = useState("")
  const [deciding, setDeciding] = useState("")
  const trimmed = name.trim()

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        className={step === "examples" ? "sm:max-w-4xl" : undefined}
      >
        {step === "name" && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (trimmed) setStep("start")
            }}
            className="space-y-4"
          >
            <DialogHeader>
              <DialogTitle>New project</DialogTitle>
              <DialogDescription>
                Give it a name and, if you can, say what you're deciding.
              </DialogDescription>
            </DialogHeader>
            <Input
              autoFocus
              value={name}
              maxLength={120}
              placeholder="For example: Refund approvals"
              onChange={(e) => setName(e.target.value)}
            />
            <div className="space-y-1.5">
              <label htmlFor="deciding" className="text-sm font-medium">
                What are you deciding?
              </label>
              <Textarea
                id="deciding"
                value={deciding}
                maxLength={1000}
                rows={2}
                placeholder="One sentence (optional)"
                onChange={(e) => setDeciding(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={!trimmed}>
                Next
              </Button>
            </DialogFooter>
          </form>
        )}
        {step === "start" && (
          <div className="space-y-4">
            <DialogHeader>
              <DialogTitle>How do you want to start?</DialogTitle>
              <DialogDescription>
                You can change everything later.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-3 sm:grid-cols-2">
              {STARTS.map((s) => (
                <button
                  key={s.mode}
                  type="button"
                  disabled={busy}
                  className="text-left disabled:opacity-50"
                  onClick={() =>
                    s.mode === "example"
                      ? setStep("examples")
                      : onStart(s.mode, trimmed, deciding.trim())
                  }
                >
                  <Card className="h-full transition-colors hover:bg-muted/50">
                    <CardHeader>
                      <CardTitle>{s.title}</CardTitle>
                      <CardDescription>{s.text}</CardDescription>
                    </CardHeader>
                  </Card>
                </button>
              ))}
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setStep("name")}>
                Back
              </Button>
            </DialogFooter>
          </div>
        )}
        {step === "examples" && (
          <div className="space-y-4">
            <DialogHeader>
              <DialogTitle>Pick an example</DialogTitle>
              <DialogDescription>
                It comes with buckets and guidelines you can edit.
              </DialogDescription>
            </DialogHeader>
            <div className="grid max-h-[60vh] gap-4 overflow-y-auto sm:grid-cols-2">
              {(templates ?? []).map((t) => (
                <TemplateCard
                  key={t.id}
                  template={t}
                  busy={busy}
                  onUse={() => onTemplate(t, trimmed)}
                />
              ))}
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setStep("start")}>
                Back
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
