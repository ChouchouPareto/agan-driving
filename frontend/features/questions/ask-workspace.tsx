"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { BookOpenCheck, ChevronDown, Heart, ListRestart, LoaderCircle, Send, Sparkles } from "lucide-react";
import { answerSchema, type QuestionDetail } from "@/lib/schemas/domain";
import { consumeSse } from "@/lib/stream/sse";
import { ApiError } from "@/lib/api/errors";
import * as api from "./api";
import { AnswerCard } from "./answer-card";
import { OCRWorkspace } from "@/features/ocr/ocr-workspace";

type LocalExchange = { id: string; user: string; assistant: string; intent: string };

export function AskWorkspace() {
  const router = useRouter();
  const params = useSearchParams();
  const savedQuestionId = params.get("questionId") ?? "";
  const savedConversationId = params.get("conversationId") ?? "";
  const savedOCRTaskId = params.get("ocrTaskId") ?? "";
  const [conversationId, setConversationId] = useState(savedConversationId);
  const [messages, setMessages] = useState<QuestionDetail[]>([]);
  const [localExchanges, setLocalExchanges] = useState<LocalExchange[]>([]);
  const [text, setText] = useState(params.get("text") ?? "");
  const [toolsOpen, setToolsOpen] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const streamEnd = useRef<HTMLDivElement | null>(null);
  const isBusy = status.startsWith("正在");

  function isExpiredSession(reason: unknown) {
    return reason instanceof ApiError && (reason.status === 401 || reason.code === "INVALID_SESSION" || reason.code === "UNAUTHORIZED");
  }

  async function returnToInvitation(draft = "") {
    if (draft) sessionStorage.setItem("super-driving-draft", draft);
    sessionStorage.setItem("super-driving-session-expired", "1");
    sessionStorage.removeItem("super-driving-conversation");
    await fetch("/api/session", { method: "DELETE" }).catch(() => undefined);
    router.replace("/enter");
  }

  function rememberConversation(id: string) {
    setConversationId(id);
    sessionStorage.setItem("super-driving-conversation", id);
    router.replace(`/ask?conversationId=${encodeURIComponent(id)}`, { scroll: false });
  }

  async function loadConversation(id: string) {
    const detail = await api.getConversation(id);
    setMessages(detail.questions);
    rememberConversation(detail.id);
  }

  useEffect(() => {
    const restore = async () => {
      try {
        if (savedQuestionId) {
          const question = await api.getQuestion(savedQuestionId);
          await loadConversation(question.conversation_id);
          return;
        }
        const id = savedConversationId || sessionStorage.getItem("super-driving-conversation") || "";
        if (id) await loadConversation(id);
      } catch (reason) {
        sessionStorage.removeItem("super-driving-conversation");
        setConversationId("");
        if (isExpiredSession(reason)) await returnToInvitation();
      }
    };
    void restore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedQuestionId, savedConversationId]);

  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    const draft = sessionStorage.getItem("super-driving-draft");
    if (draft && !text) window.setTimeout(() => {
      setText(draft);
      sessionStorage.removeItem("super-driving-draft");
    }, 0);
    // Restore a message only once after authentication.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { streamEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, localExchanges, status]);

  async function streamAnswer(questionId: string) {
    setStatus("正在查找可信依据…");
    controller.current = new AbortController();
    const response = await api.streamQuestion(questionId, controller.current.signal);
    await consumeSse(response, frame => {
      if (frame.event === "status") setStatus("正在组织答案并检查一致性…");
      if (frame.event === "done") {
        const answer = answerSchema.parse(frame.data);
        setMessages(items => items.map(item => item.id === questionId ? { ...item, answer, status: answer.evidence.length ? "ANSWERED" : "NEEDS_REVIEW" } : item));
        setStatus("");
      }
      if (frame.event === "error") {
        const parsed = api.streamErrorSchema.safeParse(frame.data);
        throw new Error(parsed.success ? parsed.data.error.message : "回答失败");
      }
    });
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const command = text.trim();
    if (isBusy || !command) return;
    setError(""); setStatus("正在识别你的意图…");
    try {
      const dispatch = await api.sendAgentMessage(conversationId, command);
      rememberConversation(dispatch.conversation_id);
      setText("");
      if (dispatch.action === "NAVIGATE" && dispatch.destination) {
        setStatus(""); router.push(dispatch.destination); return;
      }
      if (dispatch.action === "RESPOND") {
        setLocalExchanges(items => [...items, { id: crypto.randomUUID(), user: command, assistant: dispatch.assistant_message ?? "", intent: dispatch.intent }]);
        setStatus(""); return;
      }
      if (!dispatch.question_id) throw new Error("未创建问题");
      const question = await api.getQuestion(dispatch.question_id);
      setMessages(items => [...items.filter(item => item.id !== question.id), question]);
      await streamAnswer(question.id);
    } catch (reason) {
      if (isExpiredSession(reason)) { await returnToInvitation(command); return; }
      if ((reason as Error).name !== "AbortError") setError(reason instanceof Error ? reason.message : "提问失败");
      setStatus("");
    }
  }

  async function feedback(question: QuestionDetail, type: "resolved" | "not_understood" | "disputed") {
    if (!question.answer || isBusy) return;
    setError("");
    try {
      await api.sendFeedback(question.answer.id, type);
      if (type === "resolved") {
        setLocalExchanges(items => [...items, { id: crypto.randomUUID(), user: "我看懂了", assistant: "太好了，这次理解已记录。你可以继续追问，或说‘我要刷题’。", intent: "RESOLVED" }]);
      } else if (type === "not_understood") {
        setStatus("正在换一种方式解释…");
        const answer = await api.explainAgain(question.answer.id);
        setMessages(items => items.map(item => item.id === question.id ? { ...item, answer } : item));
      } else await createReviewTicket(question);
    } catch (reason) { if (isExpiredSession(reason)) await returnToInvitation(); else setError(reason instanceof Error ? reason.message : "操作失败"); }
    finally { setStatus(""); }
  }

  async function createReviewTicket(question: QuestionDetail) {
    const created = await api.createTicket(question.id, question.answer?.risk_codes ?? []);
    const ticket = await api.getTicket(created.id);
    setMessages(items => items.map(item => item.id === question.id ? { ...item, ticket } : item));
  }

  function trackOCRTask(taskId: string) {
    router.replace(`/ask?ocrTaskId=${encodeURIComponent(taskId)}${conversationId ? `&conversationId=${encodeURIComponent(conversationId)}` : ""}`, { scroll: false });
  }

  async function useOCRQuestion(questionId: string) {
    try {
      const question = await api.getQuestion(questionId);
      rememberConversation(question.conversation_id);
      setMessages(items => [...items.filter(item => item.id !== question.id), question]);
      await streamAnswer(question.id);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "图片提问失败"); setStatus(""); }
  }

  return <div className="chatPage">
    <section className="chatStream" aria-label="与超级陪驾的对话" aria-busy={isBusy}>
      <div className="assistantMessage"><span className="assistantAvatar" aria-hidden="true"><Sparkles size={18}/></span><div><span className="messageAuthor">超级陪驾 · AI</span><p>嗨，我可以帮你讲题、识别题目图片，也可以直接带你开始刷题。</p><div className="promptSuggestions"><button onClick={() => setText("我要刷题")}>我要刷题</button><button onClick={() => setText("直行车道可以右转吗？")}>问一道题</button></div></div></div>
      {messages.map(question => <div className="conversationTurn" key={question.id}>
        <div className="userMessage"><p>{question.text}</p></div>
        {question.intent === "FOLLOW_UP" && <span className="intentBadge">已结合上一题理解</span>}
        {question.answer && <AnswerCard answer={question.answer} ticket={question.ticket} busy={isBusy} onFeedback={type => feedback(question, type)} onTicket={() => createReviewTicket(question)}/>}
      </div>)}
      {localExchanges.map(item => <div className="conversationTurn" key={item.id}><div className="userMessage"><p>{item.user}</p></div><div className="assistantMessage"><span className="assistantAvatar" aria-hidden="true"><Sparkles size={16}/></span><div><span className="messageAuthor">超级陪驾 · {item.intent}</span><p>{item.assistant}</p></div></div></div>)}
      {status && <div className="assistantMessage compact" aria-live="polite"><span className="assistantAvatar" aria-hidden="true"><Sparkles size={16}/></span><div className="status"><span className="dot"/>{status}</div></div>}
      {error && <div className="chatError" role="alert">{error}</div>}
      <div ref={streamEnd}/>
    </section>
    <section id="ask-composer" className="chatComposer">
      <div className={`toolTray ${toolsOpen ? "open" : ""}`}><button className="toolTrayToggle" type="button" aria-expanded={toolsOpen} onClick={() => setToolsOpen(value => !value)}><BookOpenCheck aria-hidden="true" size={18}/><span>学习工具</span><ChevronDown aria-hidden="true" size={17}/></button>{toolsOpen && <nav className="toolTrayLinks" aria-label="学习工具"><Link href="/practice"><BookOpenCheck aria-hidden="true" size={18}/>顺序刷题</Link><Link href="/practice?mode=wrong"><ListRestart aria-hidden="true" size={18}/>错题本</Link><Link href="/practice?mode=favorites"><Heart aria-hidden="true" size={18}/>收藏题</Link></nav>}</div>
      <form className="chatInputBox" onSubmit={ask}><label className="srOnly" htmlFor="question">给超级陪驾发消息</label><textarea id="question" value={text} onChange={event => setText(event.target.value)} placeholder="发消息、粘贴题目，或说‘我要刷题’" maxLength={2000}/><div className="chatInputActions"><OCRWorkspace initialTaskId={savedOCRTaskId} onTaskCreated={trackOCRTask} onQuestionCreated={useOCRQuestion}/><span className="characterCount">{text.length}/2000</span><button className="chatSendButton" type="submit" aria-label="发送消息" disabled={isBusy || !text.trim()}>{isBusy ? <LoaderCircle aria-hidden="true" className="spin" size={19}/> : <Send aria-hidden="true" size={19}/>}</button></div></form>
      <p className="aiDisclaimer">超级陪驾会先识别意图，科目一结论以当前题库依据为准。</p>
    </section>
  </div>;
}
