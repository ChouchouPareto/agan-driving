import { z } from "zod";
import { API_ROOT, idempotencyKey, request } from "@/lib/api/client";
import { toApiError } from "@/lib/api/errors";
import { agentDispatchSchema, answerSchema, conversationDetailSchema, conversationSchema, feedbackSchema, questionCreatedSchema, questionDetailSchema, ticketCreatedSchema, ticketSchema } from "@/lib/schemas/domain";
export const createConversation = () => request("/conversations", conversationSchema, { method: "POST", body: "{}", headers: { "Idempotency-Key": idempotencyKey() } });
export const createQuestion = (conversationId: string, text: string) => request("/questions", questionCreatedSchema, { method: "POST", body: JSON.stringify({ conversation_id: conversationId, text }), headers: { "Idempotency-Key": idempotencyKey() } });
export const sendAgentMessage = (conversationId: string, text: string, licenseType = "C1", subject = "subject-1") => request("/agent/messages", agentDispatchSchema, { method: "POST", body: JSON.stringify({ conversation_id: conversationId || null, text, license_type: licenseType, subject }) });
export const getConversation = (conversationId: string) => request(`/conversations/${conversationId}`, conversationDetailSchema);
export const streamQuestion = async (questionId: string, signal?: AbortSignal) => {
  const response = await fetch(`${API_ROOT}/questions/${questionId}/stream`, { signal });
  if (!response.ok) throw await toApiError(response);
  return response;
};
export const getQuestion = (questionId: string) => request(`/questions/${questionId}`, questionDetailSchema);
export const sendFeedback = (answerId: string, type: string) => request(`/answers/${answerId}/feedback`, feedbackSchema, { method: "POST", body: JSON.stringify({ type }) });
export const explainAgain = (answerId: string) => request(`/answers/${answerId}/explain-again`, answerSchema, { method: "POST" });
export const createTicket = (questionId: string, riskCodes: string[]) => request("/review-tickets", ticketCreatedSchema, { method: "POST", body: JSON.stringify({ question_id: questionId, risk_codes: riskCodes }), headers: { "Idempotency-Key": idempotencyKey() } });
export const getTicket = (ticketId: string) => request(`/review-tickets/${ticketId}`, ticketSchema);
export const streamErrorSchema = z.object({ error: z.object({ message: z.string() }) });
