import { describe, expect, it } from "vitest";
import { answerSchema } from "@/lib/schemas/domain";
describe("answerSchema", () => { it("拒绝缺少正式答案的响应", () => { const parsed = answerSchema.safeParse({ id: "1", evidence: [] }); expect(parsed.success).toBe(false); }); });
