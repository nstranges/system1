export interface SseEvent {
  event: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- payload shape depends on the event
  data: any
}

// POST-based SSE reader. EventSource cannot send an Authorization header or a
// request body, so the stream is parsed from a fetch response by hand.
export async function streamEvents(
  url: string,
  body: unknown,
  token: string,
  onEvent: (e: SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`stream failed: ${res.status}`)

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ""
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += value
    // Events end with a blank line; tolerate CRLF.
    const frames = buffer.replace(/\r\n/g, "\n").split("\n\n")
    buffer = frames.pop() ?? ""
    for (const frame of frames) {
      const parsed = parseFrame(frame)
      if (parsed) onEvent(parsed)
    }
  }
  const tail = parseFrame(buffer.replace(/\r\n/g, "\n"))
  if (tail) onEvent(tail)
}

function parseFrame(frame: string): SseEvent | null {
  let event = "message"
  const data: string[] = []
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim()
    else if (line.startsWith("data:"))
      data.push(line.slice(5).replace(/^ /, ""))
  }
  if (data.length === 0) return null
  const text = data.join("\n")
  try {
    return { event, data: JSON.parse(text) }
  } catch {
    return { event, data: text }
  }
}
