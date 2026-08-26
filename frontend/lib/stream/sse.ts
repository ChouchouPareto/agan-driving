export type StreamFrame = { event: string; data: unknown };
export function parseFrames(buffer: string): { frames: StreamFrame[]; remainder: string } {
  const chunks = buffer.replaceAll("\r\n", "\n").split("\n\n"); const remainder = chunks.pop() ?? "";
  const frames = chunks.flatMap((chunk) => { let event = "message"; const data: string[] = []; for (const line of chunk.split("\n")) { if (line.startsWith("event:")) event = line.slice(6).trim(); if (line.startsWith("data:")) data.push(line.slice(5).trimStart()); } if (!data.length) return []; try { return [{ event, data: JSON.parse(data.join("\n")) }]; } catch { return [{ event, data: data.join("\n") }]; } });
  return { frames, remainder };
}
export async function consumeSse(response: Response, onFrame: (frame: StreamFrame) => void) {
  if (!response.ok || !response.body) throw new Error("回答服务暂时不可用");
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
  while (true) { const { done, value } = await reader.read(); buffer += decoder.decode(value, { stream: !done }); const parsed = parseFrames(buffer); buffer = parsed.remainder; parsed.frames.forEach(onFrame); if (done) break; }
}
