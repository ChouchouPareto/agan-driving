"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { LoaderCircle, Send } from "lucide-react";
import { answerSchema, type Answer, type Ticket } from "@/lib/schemas/domain";
import { consumeSse } from "@/lib/stream/sse";
import * as api from "./api";
import { AnswerCard } from "./answer-card";

export function AskWorkspace() {
  const router = useRouter(); const params = useSearchParams();
  const savedQuestionId = params.get("questionId") ?? "";
  const [conversationId, setConversationId] = useState(""); const [questionId, setQuestionId] = useState(savedQuestionId);
  const [text, setText] = useState("驾驶机动车通过没有交通信号的交叉路口怎样行驶？"); const [answer, setAnswer] = useState<Answer | null>(null); const [ticket, setTicket] = useState<Ticket | null>(null);
  const [status, setStatus] = useState(savedQuestionId ? "正在恢复上次问题…" : ""); const [error, setError] = useState(""); const controller = useRef<AbortController | null>(null);
  useEffect(() => { if (savedQuestionId) { api.getQuestion(savedQuestionId).then(detail => { setText(detail.text); setAnswer(detail.answer); setTicket(detail.ticket); setStatus(detail.answer || detail.ticket ? "" : "问题已提交，可以重新发起回答。"); }).catch(reason => { setStatus(""); setError(reason instanceof Error ? reason.message : "恢复失败"); }); } return () => controller.current?.abort(); }, [savedQuestionId]);
  async function ask(event: FormEvent) {
    event.preventDefault(); if (status || text.trim().length < 2) return; setError(""); setAnswer(null); setTicket(null); setStatus("正在准备问题…");
    try {
      let cid = conversationId; if (!cid) { const conversation = await api.createConversation(); cid = conversation.id; setConversationId(cid); }
      const question = await api.createQuestion(cid, text.trim()); setQuestionId(question.id); router.replace(`/ask?questionId=${encodeURIComponent(question.id)}`, { scroll: false }); setStatus("正在查找可信依据…");
      controller.current = new AbortController(); const response = await api.streamQuestion(question.id, controller.current.signal);
      await consumeSse(response, frame => { if (frame.event === "status") setStatus("正在组织答案并检查一致性…"); if (frame.event === "done") { setAnswer(answerSchema.parse(frame.data)); setStatus(""); } if (frame.event === "error") { const parsed = api.streamErrorSchema.safeParse(frame.data); throw new Error(parsed.success ? parsed.data.error.message : "回答失败"); } });
    } catch (reason) { if ((reason as Error).name !== "AbortError") { setStatus(""); setError(reason instanceof Error ? reason.message : "提问失败"); } }
  }
  async function feedback(type: "resolved" | "not_understood" | "disputed") { if (!answer) return; setError(""); try { await api.sendFeedback(answer.id, type); if (type === "resolved") setStatus("已记录：这个问题解决了。"); else if (type === "not_understood") { setStatus("正在换一种方式解释…"); setAnswer(await api.explainAgain(answer.id)); setStatus(""); } else await createReviewTicket(["USER_DISPUTE"]); } catch (reason) { setStatus(""); setError(reason instanceof Error ? reason.message : "操作失败"); } }
  async function createReviewTicket(risks = answer?.risk_codes ?? []) { if (!questionId) return; setError(""); try { const created = await api.createTicket(questionId, risks); setTicket(await api.getTicket(created.id)); } catch (reason) { setError(reason instanceof Error ? reason.message : "提交失败"); } }
  return <><section className="hero"><h1>今天有什么没看懂？</h1><p>先给结论，再讲原因；没有可靠依据时不会猜。</p></section><form className="card" onSubmit={ask}><label className="label" htmlFor="question">输入题目或科目一问题</label><textarea id="question" className="input" value={text} onChange={e => setText(e.target.value)} minLength={2} maxLength={2000} required/><div className="composerMeta"><span>{text.length}/2000</span><button className="button primary" type="submit" disabled={Boolean(status) || text.trim().length < 2}>{status ? <><LoaderCircle aria-hidden="true" className="spin" size={18}/>处理中</> : <><Send aria-hidden="true" size={18}/>提交问题</>}</button></div></form>{status && <div className="card status" aria-live="polite"><span className="dot"/>{status}</div>}{error && <div className="card error" role="alert">{error}</div>}{answer && <AnswerCard answer={answer} ticket={ticket} busy={Boolean(status)} onFeedback={feedback} onTicket={() => createReviewTicket()}/>}</>;
}
