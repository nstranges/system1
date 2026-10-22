import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

const repoRoot = path.resolve(__dirname, "../..")

export default defineConfig(({ mode }) => {
  // The repo-root .env also holds server secrets, so expose exactly one value.
  const env = loadEnv(mode, repoRoot, "")
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
    define: {
      "import.meta.env.VITE_CLERK_PUBLISHABLE_KEY": JSON.stringify(
        env.CLERK_PUBLISHABLE_KEY ?? "",
      ),
    },
    server: {
      proxy: {
        "/api": "http://localhost:8000",
        "/v1": "http://localhost:8000",
      },
    },
  }
})
