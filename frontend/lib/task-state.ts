export type TaskState = "idle" | "submitting" | "queued" | "running" | "streaming" | "waiting_user" | "succeeded" | "failed" | "disconnected" | "stale";
export function mapTaskState(status: string): TaskState {
  if (["SUBMITTED", "QUEUED", "NEEDS_REVIEW"].includes(status)) return "queued";
  if (["ROUTING", "RETRIEVING", "GENERATING", "VALIDATING", "PROCESSING"].includes(status)) return "running";
  if (["ANSWERED", "REPLIED", "CLOSED"].includes(status)) return "succeeded";
  if (["FAILED", "REFUSED"].includes(status)) return "failed";
  return "stale";
}
