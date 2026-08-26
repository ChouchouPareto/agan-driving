import { describe, expect, it } from "vitest";
import { parseFrames } from "@/lib/stream/sse";
describe("parseFrames", () => {
  it("保留未完整帧并解析完整帧", () => { const result = parseFrames('event: status\ndata: {"status":"ROUTING"}\n\nevent: done\ndata: {"id"'); expect(result.frames).toEqual([{ event: "status", data: { status: "ROUTING" } }]); expect(result.remainder).toContain("event: done"); });
  it("兼容 CRLF 和多行 data", () => { const result = parseFrames("event: note\r\ndata: hello\r\ndata: world\r\n\r\n"); expect(result.frames[0]).toEqual({ event: "note", data: "hello\nworld" }); });
});
