import { useAuth } from "@clerk/react"
import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { useApi } from "@/lib/api/client"
import {
  readProblem,
  type ApiKeyCreated,
  type ApiKeyOut,
  type PolicyOut,
  type Project,
  type Sample,
  type TrainedModel,
} from "@/lib/api/types"
import { ModelList } from "@/features/models/ModelList"
import { TryCanvas } from "@/features/playground/TryCanvas"
import { snippets, type SnippetLang } from "./snippets"

const LANES = [
  { id: "sys1", label: "Your model", needsModel: true },
  { id: "jev", label: "Jev with your rules", needsModel: false },
  { id: "auto", label: "Auto", needsModel: true },
] as const

const LANGS: { id: SnippetLang; label: string }[] = [
  { id: "curl", label: "curl" },
  { id: "python", label: "Python" },
  { id: "javascript", label: "JavaScript" },
]

const GENERIC_SAMPLE = "Paste the text you want a decision on here."

function sampleInput(s: Sample | undefined): string {
  if (!s) return GENERIC_SAMPLE
  const st = s.state
  if (st && typeof st === "object" && !Array.isArray(st)) {
    const ticket = (st as Record<string, unknown>).ticket as
      { subject?: string; body?: string } | undefined
    if (ticket && (ticket.subject || ticket.body)) {
      return [ticket.subject, ticket.body].filter(Boolean).join("\n\n")
    }
  }
  return typeof st === "string" ? st : JSON.stringify(st)
}

export function UseCanvas({
  project,
  policy,
  onProject,
}: {
  project: Project
  policy: PolicyOut
  onProject: (p: Project) => void
}) {
  const api = useApi()
  const { orgRole } = useAuth()
  const isAdmin = orgRole === "org:admin"
  const [keys, setKeys] = useState<ApiKeyOut[]>([])
  const [created, setCreated] = useState<ApiKeyCreated | null>(null)
  const [sys1, setSys1] = useState(false)
  const [needsLive, setNeedsLive] = useState(false)
  const [models, setModels] = useState<TrainedModel[]>([])
  const [sample, setSample] = useState<Sample | undefined>()
  const [lang, setLang] = useState<SnippetLang>("curl")
  const [busy, setBusy] = useState(false)
  const keyRef = useRef<HTMLElement>(null)

  const loadKeys = useCallback(async () => {
    const { data } = await api.GET("/api/projects/{project_id}/keys", {
      params: { path: { project_id: project.id } },
    })
    setKeys(data ?? [])
  }, [api, project.id])

  const loadModels = useCallback(async () => {
    const { data } = await api.GET("/api/models", {
      params: { query: { project_id: project.id } },
    })
    setModels(data ?? [])
  }, [api, project.id])

  // A training run that finished since the workspace loaded may have made a model live.
  useEffect(() => {
    void api
      .GET("/api/projects/{project_id}", {
        params: { path: { project_id: project.id } },
      })
      .then(({ data }) => data && onProject(data))
  }, [api, onProject, project.id])

  useEffect(() => {
    void loadKeys()
    void loadModels()
    void api.GET("/api/config").then(({ data }) => {
      setSys1(data?.sys1_available ?? false)
      setNeedsLive(data?.sys1_needs_live_model ?? false)
    })
    // Only flagship templates have samples; others answer 404, so use the generic text.
    void api
      .GET("/api/projects/{project_id}/samples", {
        params: { path: { project_id: project.id } },
      })
      .then(({ data }) => setSample(data?.[0]))
  }, [api, loadKeys, loadModels, project.id])

  async function createKey() {
    setBusy(true)
    const { data, error } = await api.POST("/api/projects/{project_id}/keys", {
      params: { path: { project_id: project.id } },
    })
    setBusy(false)
    if (!data) return void toast.error(readProblem(error).message)
    setCreated(data)
    void loadKeys()
  }

  async function revoke(id: string) {
    const { response, error } = await api.DELETE(
      "/api/projects/{project_id}/keys/{key_id}",
      { params: { path: { project_id: project.id, key_id: id } } },
    )
    if (!response.ok) return void toast.error(readProblem(error).message)
    if (created?.id === id) setCreated(null)
    void loadKeys()
  }

  async function copy(text: string, target?: HTMLElement | null) {
    try {
      await navigator.clipboard.writeText(text)
      toast("Copied")
    } catch {
      // Clipboard can be blocked: select the text so Ctrl+C works.
      if (target) window.getSelection()?.selectAllChildren(target)
      toast("Press Ctrl+C to copy")
    }
  }

  async function pickLane(lane: string) {
    const { data, error } = await api.PATCH("/api/projects/{project_id}", {
      params: { path: { project_id: project.id } },
      body: { default_lane: lane as "jev" | "sys1" | "auto" },
    })
    if (data) onProject(data)
    else toast.error(readProblem(error).message)
  }

  async function setEndpoint(enabled: boolean) {
    const { data, error } = await api.PATCH("/api/projects/{project_id}", {
      params: { path: { project_id: project.id } },
      body: { endpoint_enabled: enabled },
    })
    if (data) onProject(data)
    else toast.error(readProblem(error).message)
  }

  // When sys1 answers with each project's own model, it's usable only once this project has a live one.
  const sys1Ready = sys1 && (!needsLive || project.live_model_id != null)
  const notReady =
    sys1 && needsLive
      ? "This project has no live model yet. Train one in the Train step."
      : "Your model isn't connected yet."
  const endpoint = `${window.location.origin}/v1/systemone`
  const code = snippets(endpoint, sampleInput(sample))[lang]

  return (
    <div className="space-y-6">
      <TryCanvas project={project} policy={policy} />

      <div className="border-t pt-6">
        <h2 className="text-xl font-semibold tracking-tight">
          Connect it to your system
        </h2>
        <p className="text-sm text-muted-foreground">
          Call the endpoint from your own app with a key, and get a decision
          back.
        </p>
      </div>

      <section className="space-y-2">
        <h3 className="font-medium">Endpoint</h3>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant={project.endpoint_enabled ? "outline" : "default"}
            disabled={!isAdmin}
            onClick={() => void setEndpoint(!project.endpoint_enabled)}
          >
            {project.endpoint_enabled ? "Turn off" : "Turn on"}
          </Button>
          <p className="text-sm text-muted-foreground">
            {project.endpoint_enabled
              ? "On: calls with your key get answers."
              : "Off: calls are refused, but your keys are kept. Turn it on to use them again."}
          </p>
        </div>
        {!isAdmin && (
          <p className="text-xs text-muted-foreground">
            Only an admin of your team can turn the endpoint on or off.
          </p>
        )}
      </section>

      {models.length > 0 && (
        <section className="space-y-2">
          <h3 className="font-medium">Your models</h3>
          <p className="text-sm text-muted-foreground">
            Each time you train, the new model is kept here. The live one is the
            one your endpoint uses.
          </p>
          <div className="rounded-lg border">
            <ModelList
              models={models}
              showProject={false}
              onLive={(p) => {
                onProject(p)
                void loadModels()
              }}
            />
          </div>
        </section>
      )}

      <section className="space-y-2">
        <h3 className="font-medium">Which one answers</h3>
        <div className="grid gap-2 sm:grid-cols-3">
          {LANES.map((l) => {
            const disabled = l.needsModel && !sys1Ready
            return (
              <label
                key={l.id}
                title={disabled ? notReady : undefined}
                className={`flex items-center gap-2 rounded-lg border p-3 text-sm ${
                  disabled ? "opacity-50" : "cursor-pointer"
                }`}
              >
                <input
                  type="radio"
                  name="lane"
                  checked={project.default_lane === l.id}
                  disabled={disabled}
                  onChange={() => void pickLane(l.id)}
                />
                {l.label}
              </label>
            )
          })}
        </div>
        {!sys1Ready && (
          <p className="text-xs text-muted-foreground">
            {notReady} Until then, only Jev with your rules is available.
          </p>
        )}
        {sys1Ready && (
          <p className="text-xs text-muted-foreground">
            Auto uses your model when it is sure, and Jev with your rules when
            it isn't. Those answers are flagged for review.
          </p>
        )}
      </section>

      <section className="space-y-2">
        <h3 className="font-medium">Your key</h3>
        {created && (
          <div className="space-y-2 rounded-lg border border-primary/40 p-3">
            <p className="text-sm">
              Copy this key now. You won't be able to see it again.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <code
                ref={keyRef}
                className="min-w-0 break-all rounded bg-muted px-2 py-1 text-sm"
              >
                {created.key}
              </code>
              <Button
                size="sm"
                onClick={() => void copy(created.key, keyRef.current)}
              >
                Copy
              </Button>
            </div>
          </div>
        )}
        <ul className="divide-y rounded-lg border">
          {keys.length === 0 && (
            <li className="p-3 text-sm text-muted-foreground">No keys yet.</li>
          )}
          {keys.map((k) => (
            <li
              key={k.id}
              className="flex items-center justify-between gap-3 p-3 text-sm"
            >
              <span>
                <code>{k.prefix}…</code>
                <span className="ml-2 text-muted-foreground">
                  made {new Date(k.created_at).toLocaleDateString()}
                </span>
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={!isAdmin}
                onClick={() => void revoke(k.id)}
              >
                Revoke
              </Button>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap items-center gap-3">
          <Button disabled={!isAdmin || busy} onClick={() => void createKey()}>
            Create a key
          </Button>
          {!isAdmin && (
            <p className="text-xs text-muted-foreground">
              Only an admin of your team can create or revoke keys.
            </p>
          )}
        </div>
      </section>

      <section className="space-y-2">
        <h3 className="font-medium">Call it</h3>
        <p className="text-sm text-muted-foreground">
          Send a POST to <code className="break-all">{endpoint}</code> with your
          key. Replace the key placeholder with the one you made.
        </p>
        <div className="flex gap-1">
          {LANGS.map((l) => (
            <Button
              key={l.id}
              size="sm"
              variant={lang === l.id ? "default" : "ghost"}
              onClick={() => setLang(l.id)}
            >
              {l.label}
            </Button>
          ))}
        </div>
        <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">
          {code}
        </pre>
        <Button size="sm" variant="outline" onClick={() => void copy(code)}>
          Copy
        </Button>
      </section>
    </div>
  )
}
