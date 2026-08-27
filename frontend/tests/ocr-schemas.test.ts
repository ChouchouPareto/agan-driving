import { describe, expect, it } from "vitest";
import { ocrTaskSchema } from "@/features/ocr/schemas";

describe("ocrTaskSchema", () => {
  it("拒绝未知字段类型", () => {
    const parsed = ocrTaskSchema.safeParse({
      id: "task",
      status: "WAITING_USER",
      request_id: "request",
      version: 1,
      question_type: "unknown",
      warnings: [],
      needs_confirmation: true,
      fields: [{ id: "field", field_type: "answer", label: null, sequence: 0, value: "x", confidence: 0.5, needs_confirmation: true, version: 1 }],
      safe_error: null,
      preview_url: "/preview",
      linked_question_id: null,
      created_at: "2026-08-27T00:00:00Z",
      updated_at: "2026-08-27T00:00:00Z",
    });
    expect(parsed.success).toBe(false);
  });
});
