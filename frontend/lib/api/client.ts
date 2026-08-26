import { z } from "zod";
import { toApiError } from "./errors";
export const API_ROOT = "/api/backend";
export async function request<T>(path: string, schema: z.ZodType<T>, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, { ...options, headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers } });
  if (!response.ok) throw await toApiError(response);
  return schema.parse(await response.json());
}
export function idempotencyKey() { return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`; }
