import { useAuth } from "@clerk/react"
import createClient, { type Middleware } from "openapi-fetch"
import { useMemo } from "react"
import type { paths } from "./schema"

// Typed API client for the server. Clerk's token is fetched per request so it
// is never stale; a signed-out user sends no Authorization header.
export function useApi() {
  const { getToken } = useAuth()
  return useMemo(() => {
    const client = createClient<paths>({ baseUrl: "" })
    const auth: Middleware = {
      async onRequest({ request }) {
        const token = await getToken()
        if (token) request.headers.set("Authorization", `Bearer ${token}`)
        return request
      },
    }
    client.use(auth)
    return client
  }, [getToken])
}
