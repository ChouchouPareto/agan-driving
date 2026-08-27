import { idempotencyKey, request } from "@/lib/api/client";
import { ocrConfirmSchema, ocrTaskSchema, uploadResultSchema } from "./schemas";
import { toApiError } from "@/lib/api/errors";

export async function uploadImage(file: File) {
  const body = new FormData();
  body.append("image", file);
  const response = await fetch("/api/backend/assets/images", { method: "POST", body });
  if (!response.ok) throw await toApiError(response);
  return uploadResultSchema.parse(await response.json());
}

export function createOCRTask(assetId: string) {
  return request("/ocr-tasks", ocrTaskSchema, {
    method: "POST",
    body: JSON.stringify({ asset_id: assetId }),
    headers: { "Idempotency-Key": idempotencyKey() },
  });
}

export function getOCRTask(taskId: string) {
  return request(`/ocr-tasks/${taskId}`, ocrTaskSchema);
}

export function saveOCRFields(task: import("./schemas").OCRTask, values: Record<string, string>) {
  return request(`/ocr-tasks/${task.id}/fields`, ocrTaskSchema, {
    method: "PATCH",
    body: JSON.stringify({
      version: task.version,
      fields: task.fields.map((field) => ({ field_id: field.id, value: values[field.id] ?? field.value })),
    }),
  });
}

export function confirmOCRTask(taskId: string) {
  return request(`/ocr-tasks/${taskId}/confirm`, ocrConfirmSchema, {
    method: "POST",
    body: JSON.stringify({}),
    headers: { "Idempotency-Key": idempotencyKey() },
  });
}
