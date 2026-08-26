import { describe, expect, it } from "vitest";
import { mapTaskState } from "@/lib/task-state";
describe("mapTaskState", () => { it("不把未知状态当作成功", () => expect(mapTaskState("NEW_PROVIDER_STATE")).toBe("stale")); it.each([["QUEUED", "queued"], ["GENERATING", "running"], ["ANSWERED", "succeeded"], ["FAILED", "failed"]])("%s => %s", (source, expected) => expect(mapTaskState(source)).toBe(expected)); });
