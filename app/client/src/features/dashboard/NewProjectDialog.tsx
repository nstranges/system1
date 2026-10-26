import {
  ArrowLeft,
  ChevronRight,
  FileSpreadsheet,
  FileText,
  LayoutTemplate,
  MessageSquare,
  type LucideIcon,
} from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import type { Template } from "@/lib/api/types"
import { TemplateCard } from "./TemplateCard"

export type StartMode = "scratch" | "upload" | "documents"

const STARTS: {
  mode: StartMode | "example"
  title: string
  text: string
  icon: LucideIcon
}[] = [
  {
    mode: "scratch",
    title: "From scratch",
    text: "Your assistant helps you describe the decision.",
    icon: MessageSquare,
  },
  {
    mode: "example",
    title: "From an example",
    text: "Start from a ready-made decision and change it.",
    icon: LayoutTemplate,
  },
  {
    mode: "upload",
    title: "From my past decisions",
    text: "Upload a file of decisions you've already made.",
    icon: FileSpreadsheet,
  },
  {
    mode: "documents",
    title: "From my documents",
    text: "Share a policy or guide and we'll read it.",
    icon: FileText,
  },
]

// Back and the main action share one plain row; the dialog's tinted footer bar
// made a lone Back button look like an afterthought.
function BackRow({ onBack }: { onBack: () => void }) {
  return (
    <div className="flex">
      <Button variant="ghost" className="-ml-2" onClick={onBack}>
        <ArrowLeft /> Back
      </Button>
    </div>
  )
}

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
        className={cn(
          "gap-5 p-6",
          step === "examples"
            ? "sm:max-w-4xl"
            : step === "start"
              ? "sm:max-w-lg"
              : "sm:max-w-md",
        )}
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
              <DialogTitle className="text-xl font-semibold tracking-tight">
                New project
              </DialogTitle>
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
            <div className="flex justify-end">
              <Button type="submit" disabled={!trimmed}>
                Next
              </Button>
            </div>
          </form>
        )}
        {step === "start" && (
          <div className="space-y-4">
            <DialogHeader>
              <DialogTitle className="text-xl font-semibold tracking-tight">
                How do you want to start?
              </DialogTitle>
              <DialogDescription>
                You can change everything later.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              {STARTS.map((s) => (
                <button
                  key={s.mode}
                  type="button"
                  disabled={busy}
                  className="group flex w-full items-center gap-4 rounded-[10px] border bg-card p-4 text-left transition-colors outline-none hover:border-foreground/25 hover:bg-muted/50 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
                  onClick={() =>
                    s.mode === "example"
                      ? setStep("examples")
                      : onStart(s.mode, trimmed, deciding.trim())
                  }
                >
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted text-foreground">
                    <s.icon className="size-5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[15px] font-medium">
                      {s.title}
                    </span>
                    <span className="block text-sm text-muted-foreground">
                      {s.text}
                    </span>
                  </span>
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </button>
              ))}
            </div>
            <BackRow onBack={() => setStep("name")} />
          </div>
        )}
        {step === "examples" && (
          <div className="space-y-4">
            <DialogHeader>
              <DialogTitle className="text-xl font-semibold tracking-tight">
                Pick an example
              </DialogTitle>
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
            <BackRow onBack={() => setStep("start")} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
