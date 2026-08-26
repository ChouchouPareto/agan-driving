import { z } from "zod";
const envelope = z.object({ error: z.object({ code: z.string().optional(), message: z.string() }).optional(), detail: z.object({ code: z.string().optional(), message: z.string() }).optional() });
export class ApiError extends Error { constructor(message: string, public status = 0, public code = "REQUEST_FAILED", public requestId?: string) { super(message); this.name = "ApiError"; } }
export async function toApiError(response: Response) {
  const parsed = envelope.safeParse(await response.clone().json().catch(() => ({})));
  const detail = parsed.success ? (parsed.data.error ?? parsed.data.detail) : undefined;
  return new ApiError(detail?.message ?? "请求失败，请稍后重试。", response.status, detail?.code, response.headers.get("x-request-id") ?? undefined);
}
