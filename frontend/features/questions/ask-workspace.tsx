"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { BookOpenCheck, ChevronDown, Heart, ListRestart, LoaderCircle, Send, Sparkles } from "lucide-react";
import { answerSchema, type Answer, type Ticket } from "@/lib/schemas/domain";
import { consumeSse } from "@/lib/stream/sse";
import * as api from "./api";
import { AnswerCard } from "./answer-card";
import { OCRWorkspace } from "@/features/ocr/ocr-workspace";

export function AskWorkspace() {
  const router = useRouter(); const params = useSearchParams();
  const savedQuestionId = params.get("questionId") ?? "";
  const savedOCRTaskId = params.get("ocrTaskId") ?? "";
  const practiceQuestion = params.get("text") ?? "";
  const [conversationId, setConversationId] = useState(""); const [questionId, setQuestionId] = useState(savedQuestionId);
  const [text, setText] = useState(practiceQuestion); const [answer, setAnswer] = useState<Answer | null>(null); const [ticket, setTicket] = useState<Ticket | null>(null); const [toolsOpen, setToolsOpen] = useState(false);
  const [status, setStatus] = useState(savedQuestionId ? "正在恢复上次问题…" : ""); const [error, setError] = useState(""); const controller = useRef<AbortController | null>(null);
  const canResumeQuestion = ["题目已确认，可以提交生成可信回答。", "问题已提交，可以重新发起回答。"].includes(status);
  useEffect(() => { if (savedQuestionId) { api.getQuestion(savedQuestionId).then(detail => { setText(detail.text); setAnswer(detail.answer); setTicket(detail.ticket); setStatus(detail.answer || detail.ticket ? "" : "问题已提交，可以重新发起回答。"); }).catch(reason => { setStatus(""); setError(reason instanceof Error ? reason.message : "恢复失败"); }); } return () => controller.current?.abort(); }, [savedQuestionId]);
  async function ask(event: FormEvent) {
    event.preventDefault(); const command=text.trim(); if (/错题/.test(command)) { router.push("/practice?mode=wrong"); return; } if (/收藏/.test(command)) { router.push("/practice?mode=favorites"); return; } if (/(刷题|练题|做题|开始练习|顺序练习)/.test(command)) { router.push("/practice"); return; } const resumable = Boolean(questionId) && ["题目已确认，可以提交生成可信回答。", "问题已提交，可以重新发起回答。"].includes(status); if ((status && !resumable) || command.length < 2) return; setError(""); setAnswer(null); setTicket(null); setStatus("正在准备问题…");
    try {
      let nextQuestionId = questionId;
      if (!resumable) {
        let cid = conversationId; if (!cid) { const conversation = await api.createConversation(); cid = conversation.id; setConversationId(cid); }
        const question = await api.createQuestion(cid, text.trim()); nextQuestionId = question.id; setQuestionId(question.id); router.replace(`/ask?questionId=${encodeURIComponent(question.id)}`, { scroll: false });
      }
      setStatus("正在查找可信依据…");
      controller.current = new AbortController(); const response = await api.streamQuestion(nextQuestionId, controller.current.signal);
      await consumeSse(response, frame => { if (frame.event === "status") setStatus("正在组织答案并检查一致性…"); if (frame.event === "done") { setAnswer(answerSchema.parse(frame.data)); setStatus(""); } if (frame.event === "error") { const parsed = api.streamErrorSchema.safeParse(frame.data); throw new Error(parsed.success ? parsed.data.error.message : "回答失败"); } });
    } catch (reason) { if ((reason as Error).name !== "AbortError") { setStatus(""); setError(reason instanceof Error ? reason.message : "提问失败"); } }
  }
  function trackOCRTask(taskId: string) { router.replace(`/ask?ocrTaskId=${encodeURIComponent(taskId)}`, { scroll: false }); }
  function useOCRQuestion(nextQuestionId: string) {
    setQuestionId(nextQuestionId);
    router.replace(`/ask?questionId=${encodeURIComponent(nextQuestionId)}`, { scroll: false });
    setStatus("题目已确认，可以提交生成可信回答。");
    api.getQuestion(nextQuestionId).then((detail) => setText(detail.text)).catch(() => undefined);
  }
  async function feedback(type: "resolved" | "not_understood" | "disputed") { if (!answer) return; setError(""); try { await api.sendFeedback(answer.id, type); if (type === "resolved") setStatus("已记录：这个问题解决了。"); else if (type === "not_understood") { setStatus("正在换一种方式解释…"); setAnswer(await api.explainAgain(answer.id)); setStatus(""); } else await createReviewTicket(["USER_DISPUTE"]); } catch (reason) { setStatus(""); setError(reason instanceof Error ? reason.message : "操作失败"); } }
  async function createReviewTicket(risks = answer?.risk_codes ?? []) { if (!questionId) return; setError(""); try { const created = await api.createTicket(questionId, risks); setTicket(await api.getTicket(created.id)); } catch (reason) { setError(reason instanceof Error ? reason.message : "提交失败"); } }
  return <div className="chatPage"><section className="chatStream" aria-label="与超级陪驾的对话"><div className="assistantMessage"><span className="assistantAvatar" aria-hidden="true"><Sparkles size={18}/></span><div><span className="messageAuthor">超级陪驾 · AI</span><p>嗨，我可以帮你讲题、识别题目图片，也可以直接带你开始刷题。</p><div className="promptSuggestions"><button onClick={()=>router.push("/practice")}>我要刷题</button><button onClick={()=>setText("直行车道可以右转吗？")}>问一道题</button></div></div></div>{questionId&&<div className="userMessage"><p>{text}</p></div>}{status&&<div className="assistantMessage compact" aria-live="polite"><span className="assistantAvatar" aria-hidden="true"><Sparkles size={16}/></span><div className="status"><span className="dot"/>{status}</div></div>}{error&&<div className="chatError" role="alert">{error}</div>}{answer&&<AnswerCard answer={answer} ticket={ticket} busy={Boolean(status)} onFeedback={feedback} onTicket={()=>createReviewTicket()}/>}</section><section id="ask-composer" className="chatComposer"><div className={`toolTray ${toolsOpen?"open":""}`}><button className="toolTrayToggle" aria-expanded={toolsOpen} onClick={()=>setToolsOpen(value=>!value)}><BookOpenCheck aria-hidden="true" size={18}/><span>学习工具</span><ChevronDown aria-hidden="true" size={17}/></button>{toolsOpen&&<nav className="toolTrayLinks" aria-label="学习工具"><Link href="/practice"><BookOpenCheck aria-hidden="true" size={18}/>顺序刷题</Link><Link href="/practice?mode=wrong"><ListRestart aria-hidden="true" size={18}/>错题本</Link><Link href="/practice?mode=favorites"><Heart aria-hidden="true" size={18}/>收藏题</Link></nav>}</div><form className="chatInputBox" onSubmit={ask}><label className="srOnly" htmlFor="question">给超级陪驾发消息</label><textarea id="question" value={text} onChange={e=>setText(e.target.value)} placeholder="发消息、粘贴题目，或说‘我要刷题’" minLength={2} maxLength={2000} required/><div className="chatInputActions"><OCRWorkspace initialTaskId={savedOCRTaskId} onTaskCreated={trackOCRTask} onQuestionCreated={useOCRQuestion}/><span className="characterCount">{text.length}/2000</span><button className="chatSendButton" type="submit" aria-label="发送消息" disabled={(Boolean(status)&&!canResumeQuestion)||text.trim().length<2}>{status&&!canResumeQuestion?<LoaderCircle aria-hidden="true" className="spin" size={19}/>:<Send aria-hidden="true" size={19}/>}</button></div></form><p className="aiDisclaimer">超级陪驾是 AI 助手，回答会引用当前题库依据。</p></section></div>;
}
