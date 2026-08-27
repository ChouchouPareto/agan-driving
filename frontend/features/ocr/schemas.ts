import { z } from "zod";

export const uploadResultSchema = z.object({
  asset_id: z.string(),
  status: z.string(),
  mime: z.string(),
  size_bytes: z.number(),
  expires_at: z.string(),
  request_id: z.string(),
});

export const ocrFieldSchema = z.object({
  id: z.string(),
  field_type: z.enum(["stem", "option"]),
  label: z.string().nullable(),
  sequence: z.number(),
  value: z.string(),
  confidence: z.number(),
  needs_confirmation: z.boolean(),
  version: z.number(),
});

export const ocrTaskSchema = z.object({
  id: z.string(),
  status: z.string(),
  request_id: z.string(),
  version: z.number(),
  question_type: z.string(),
  warnings: z.array(z.string()),
  needs_confirmation: z.boolean(),
  fields: z.array(ocrFieldSchema),
  safe_error: z.object({ code: z.string().nullable(), message: z.string().nullable() }).nullable(),
  preview_url: z.string(),
  linked_question_id: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const ocrConfirmSchema = z.object({
  ocr_task_id: z.string(),
  question_id: z.string(),
  status: z.literal("QUESTION_CREATED"),
});

export type OCRTask = z.infer<typeof ocrTaskSchema>;
