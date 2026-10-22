export type SnippetLang = "curl" | "python" | "javascript"

// The sample body is whatever the user can paste back into their own system:
// a JSON string literal keeps quotes and newlines safe in all three snippets.
export function snippets(
  endpoint: string,
  sample: string,
): Record<SnippetLang, string> {
  const text = JSON.stringify(sample)
  const body = `{"state": ${text}}`
  return {
    curl: `curl -X POST ${endpoint} \\
  -H "Authorization: Bearer $SYS1_KEY" \\
  -H "Content-Type: application/json" \\
  -d '${body.replace(/'/g, `'\\''`)}'`,
    python: `import requests

res = requests.post(
    "${endpoint}",
    headers={"Authorization": "Bearer YOUR_KEY"},
    json={"state": ${text}},
)
print(res.json()["answers"])`,
    javascript: `const res = await fetch("${endpoint}", {
  method: "POST",
  headers: {
    Authorization: "Bearer YOUR_KEY",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ state: ${text} }),
})
const { answers, system1 } = await res.json()`,
  }
}
