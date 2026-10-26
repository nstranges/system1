import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react"
import { useApi } from "@/lib/api/client"
import type { ProjectProgress } from "@/lib/api/types"

export function useProgress(projectId: string): {
  progress: ProjectProgress | null
  reload: () => void
} {
  const api = useApi()
  const [progress, setProgress] = useState<ProjectProgress | null>(null)

  const reload = useCallback(() => {
    // A failed fetch keeps whatever was showing: stale progress beats none.
    void api
      .GET("/api/projects/{project_id}/progress", {
        params: { path: { project_id: projectId } },
      })
      .then(({ data }) => {
        if (data) setProgress(data)
      })
      .catch(() => undefined)
  }, [api, projectId])

  useEffect(() => {
    reload()
  }, [reload])

  return { progress, reload }
}

// Canvases call this after a change that can move a stage's status.
export const ProgressReloadContext = createContext<() => void>(() => {})

export function useProgressReload(): () => void {
  return useContext(ProgressReloadContext)
}
