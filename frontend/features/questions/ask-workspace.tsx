"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowRight, BookOpenCheck, Camera, CheckCircle2, Database, Heart, History, ImageUp, LoaderCircle, MessageCircleQuestion, Plus, Send, Sparkles, X } from "lucide-react";
import { answerSchema, type QuestionDetail } from "@/lib/schemas/domain";
import { consumeSse } from "@/lib/stream/sse";
import { ApiError } from "@/lib/api/errors";
import * as api from "./api";
import { AnswerCard } from "./answer-card";
import { OCRWorkspace } from "@/features/ocr/ocr-workspace";

type LocalExchange = { id: string; user: string; assistant: string; intent: string; destination?: string };
type KnowledgeStatus = { connected: boolean; version: string | null; item_count: number; scope: string; is_preview: boolean; notice: string };
const learnerVoices = [
  { label: "我的驾驶证怎么还没有拿出来？", prompt: "我的驾驶证怎么还没有拿出来？" },
  { label: "科目一又挂了怎么办？", prompt: "科目一又挂了怎么办？" },
  { label: "我该买梅赛德斯还是凯迪拉克？", prompt: "我该买梅赛德斯还是凯迪拉克？" },
];

export function AskWorkspace() {
  const router = useRouter();
  const params = useSearchParams();
  const savedQuestionId = params.get("questionId") ?? "";
  const savedConversationId = params.get("conversationId") ?? "";
  const savedOCRTaskId = params.get("ocrTaskId") ?? "";
  const isNewConversation = params.get("new") === "1";
  const licenseType = params.get("license") ?? "C1";
  const subject = params.get("subject") ?? "subject-1";
  const [conversationId, setConversationId] = useState(savedConversationId);
  const [messages, setMessages] = useState<QuestionDetail[]>([]);
  const [localExchanges, setLocalExchanges] = useState<LocalExchange[]>([]);
  const [text, setText] = useState(params.get("text") ?? "");
  const [toolsOpen, setToolsOpen] = useState(false);
  const [pendingUser, setPendingUser] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [knowledge, setKnowledge] = useState<KnowledgeStatus | null>(null);
  const [voiceIndex, setVoiceIndex] = useState(0);
  const [voicePaused, setVoicePaused] = useState(false);
  const [resolvedAnswerIds, setResolvedAnswerIds] = useState<Set<string>>(() => new Set());
  const controller = useRef<AbortController | null>(null);
  const chatStream = useRef<HTMLElement | null>(null);
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
  }

  function syncConversationUrl(id: string) {
    window.history.replaceState(null, "", `/ask?conversationId=${encodeURIComponent(id)}`);
  }

  async function loadConversation(id: string) {
    const detail = await api.getConversation(id);
    setMessages(detail.questions);
    rememberConversation(detail.id);
  }

  useEffect(() => {
    const restore = async () => {
      try {
        if (isNewConversation) {
          sessionStorage.removeItem("super-driving-conversation");
          setConversationId("");
          setMessages([]);
          setLocalExchanges([]);
          return;
        }
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
  }, [savedQuestionId, savedConversationId, isNewConversation]);

  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    const hasContent = messages.length > 0 || localExchanges.length > 0 || Boolean(pendingUser || status || error);
    if (hasContent || voicePaused || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setVoiceIndex(value => (value + 1) % learnerVoices.length), 5200);
    return () => window.clearInterval(timer);
  }, [messages.length, localExchanges.length, pendingUser, status, error, voicePaused]);
  useEffect(() => {
    fetch("/api/backend/knowledge/status", { cache: "no-store" }).then(async response => {
      if (response.ok) setKnowledge(await response.json() as KnowledgeStatus);
    }).catch(() => undefined);
  }, [licenseType, subject]);
  useEffect(() => {
    const draft = sessionStorage.getItem("super-driving-draft");
    if (draft && !text) window.setTimeout(() => {
      setText(draft);
      sessionStorage.removeItem("super-driving-draft");
    }, 0);
    // Restore a message only once after authentication.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    const container = chatStream.current;
    if (!container) return;
    const frame = window.requestAnimationFrame(() => {
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      container.scrollTo({ top: container.scrollHeight, behavior: reduceMotion ? "auto" : "smooth" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages, localExchanges, pendingUser, status, error]);

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
    setError(""); setPendingUser(command); setText(""); setStatus("正在识别你的意图…");
    try {
      const dispatch = await api.sendAgentMessage(conversationId, command, licenseType, subject);
      rememberConversation(dispatch.conversation_id);
      if (dispatch.action === "NAVIGATE" && dispatch.destination) {
        const separator = dispatch.destination.includes("?") ? "&" : "?";
        setPendingUser(""); setStatus(""); router.push(`${dispatch.destination}${separator}license=${licenseType}&subject=${subject}`); return;
      }
      if (dispatch.action === "RESPOND" || dispatch.action === "SUGGEST_NAVIGATION") {
        setLocalExchanges(items => [...items, { id: crypto.randomUUID(), user: command, assistant: dispatch.assistant_message ?? "", intent: dispatch.intent, destination: dispatch.destination ?? undefined }]);
        syncConversationUrl(dispatch.conversation_id);
        setPendingUser(""); setStatus(""); return;
      }
      if (!dispatch.question_id) throw new Error("未创建问题");
      const question = await api.getQuestion(dispatch.question_id);
      setMessages(items => [...items.filter(item => item.id !== question.id), question]);
      setPendingUser("");
      await streamAnswer(question.id);
      syncConversationUrl(dispatch.conversation_id);
    } catch (reason) {
      if (isExpiredSession(reason)) { await returnToInvitation(command); return; }
      if ((reason as Error).name !== "AbortError") setError(reason instanceof Error ? reason.message : "提问失败");
      setPendingUser(""); setText(command);
      setStatus("");
    }
  }

  async function feedback(question: QuestionDetail, type: "resolved" | "not_understood" | "disputed") {
    if (!question.answer || isBusy) return;
    if (type === "resolved" && resolvedAnswerIds.has(question.answer.id)) return;
    setError("");
    try {
      await api.sendFeedback(question.answer.id, type);
      if (type === "resolved") {
        setResolvedAnswerIds(ids => new Set(ids).add(question.answer!.id));
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

  function openImagePicker() {
    setToolsOpen(false);
    window.setTimeout(() => document.querySelector<HTMLInputElement>(".ocrPanel input[type='file']")?.click(), 0);
  }

  async function useOCRQuestion(questionId: string) {
    try {
      const question = await api.getQuestion(questionId);
      rememberConversation(question.conversation_id);
      setMessages(items => [...items.filter(item => item.id !== question.id), question]);
      await streamAnswer(question.id);
      syncConversationUrl(question.conversation_id);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "图片提问失败"); setStatus(""); }
  }

  const hasConversation = messages.length > 0 || localExchanges.length > 0 || Boolean(pendingUser || status || error);

  return <div className={`chatPage ${hasConversation ? "hasConversation" : "isWelcome"}`}>
    <section ref={chatStream} className="chatStream" aria-label="与超级驾陪的对话" aria-busy={isBusy}>
      {!hasConversation && <div className="welcomePanel"><span className="welcomeEyebrow">C1 科目一 · AI 学习伙伴</span><h1>Hi，我是超级驾陪</h1><p>比起只告诉你答案，我更想陪你真正看懂。今天想先学什么？</p>{knowledge && <div className={`knowledgeConnection ${knowledge.connected ? "connected" : ""}`} title={knowledge.notice}><Database aria-hidden="true"/><span>{knowledge.connected ? `已连接 ${knowledge.item_count.toLocaleString("zh-CN")} 道 ${knowledge.scope} 知识库` : "知识库暂未连接"}</span>{knowledge.is_preview && knowledge.connected && <b>预览版</b>}</div>}<section className="homePrompts" aria-label="开始学习"><button className="homePrompt compact" onClick={() => setText("给我出 5 道科目一题")}><strong>给我出 5 道科目一题</strong><ArrowRight aria-hidden="true"/></button><div className="learnerVoice" aria-label="学员常见心声" onMouseEnter={() => setVoicePaused(true)} onMouseLeave={() => setVoicePaused(false)} onFocusCapture={() => setVoicePaused(true)} onBlurCapture={() => setVoicePaused(false)}><button key={voiceIndex} onClick={() => setText(learnerVoices[voiceIndex].prompt)}><strong>{learnerVoices[voiceIndex].label}</strong><ArrowRight aria-hidden="true"/></button></div><button className="homePrompt compact" onClick={() => setText("复习一下我的错题")}><strong>复习一下我的错题</strong><ArrowRight aria-hidden="true"/></button></section></div>}
      {messages.map(question => <div className="conversationTurn" key={question.id}>
        <div className="userMessage"><p>{question.text}</p></div>
        {question.intent === "FOLLOW_UP" && <span className="intentBadge">已结合上一题理解</span>}
        {question.answer && <AnswerCard answer={question.answer} ticket={question.ticket} busy={isBusy} resolved={resolvedAnswerIds.has(question.answer.id)} onFeedback={type => feedback(question, type)} onTicket={() => createReviewTicket(question)}/>}
      </div>)}
      {localExchanges.map(item => <div className="conversationTurn" key={item.id}><div className="userMessage"><p>{item.user}</p></div><div className="assistantMessage"><span className="assistantAvatar" aria-hidden="true"><Sparkles size={16}/></span><div><span className="messageAuthor">超级驾陪 · 学车伙伴</span><p>{item.assistant}</p>{item.destination && <button className="navigationSuggestion" onClick={() => { const separator = item.destination!.includes("?") ? "&" : "?"; router.push(`${item.destination}${separator}license=${licenseType}&subject=${subject}`); }}>{item.intent === "MOCK_EXAM" ? "开始模拟考试" : item.intent === "WRONG_QUESTIONS" ? "打开错题本" : item.intent === "FAVORITES" ? "查看收藏题" : "开始刷题"}<ArrowRight aria-hidden="true" size={17}/></button>}</div></div></div>)}
      {pendingUser && <div className="conversationTurn pendingTurn"><div className="userMessage"><p>{pendingUser}</p></div></div>}
      {status && <div className="assistantMessage compact" aria-live="polite"><span className="assistantAvatar" aria-hidden="true"><Sparkles size={16}/></span><div className="status"><span className="dot"/>{status}</div></div>}
      {error && <div className="chatError" role="alert">{error}</div>}
    </section>
    <section id="ask-composer" className="chatComposer">
      <nav className="quickTools" aria-label="快捷学习入口"><Link href={`/practice?license=${licenseType}&subject=${subject}`}><BookOpenCheck aria-hidden="true"/>顺序刷题</Link><Link href={`/exam?license=${licenseType}&subject=${subject}`}><CheckCircle2 aria-hidden="true"/>模拟考试</Link><Link href={`/practice?mode=wrong&license=${licenseType}&subject=${subject}`}><History aria-hidden="true"/>错题本</Link><Link href={`/practice?mode=favorites&license=${licenseType}&subject=${subject}`}><Heart aria-hidden="true"/>收藏题</Link><button type="button" onClick={openImagePicker}><ImageUp aria-hidden="true"/>拍题问 AI</button></nav>
      <form className="chatInputBox" onSubmit={ask}><label className="srOnly" htmlFor="question">给超级驾陪发消息</label><textarea id="question" value={text} onChange={event => setText(event.target.value)} placeholder="发消息或按住说话" maxLength={300}/><div className="chatInputActions"><button className="composerIconButton" type="button" aria-label={toolsOpen ? "收起学习工具" : "展开学习工具"} aria-expanded={toolsOpen} onClick={() => setToolsOpen(value => !value)}>{toolsOpen ? <X aria-hidden="true"/> : <Plus aria-hidden="true"/>}</button><OCRWorkspace initialTaskId={savedOCRTaskId} onTaskCreated={trackOCRTask} onQuestionCreated={useOCRQuestion}/><span className="characterCount">{text.length}/300</span><button className="chatSendButton" type="submit" aria-label="发送消息" disabled={isBusy || !text.trim()}>{isBusy ? <LoaderCircle aria-hidden="true" className="spin" size={20}/> : <Send aria-hidden="true" size={20}/>}</button></div></form>
      {toolsOpen && <div className="mobileToolSheet" aria-label="学习工具"><Link href={`/practice?license=${licenseType}&subject=${subject}`}><span><BookOpenCheck aria-hidden="true"/></span><strong>顺序刷题</strong><small>按题库持续练习</small></Link><Link href={`/practice?mode=wrong&license=${licenseType}&subject=${subject}`}><span><History aria-hidden="true"/></span><strong>错题本</strong><small>集中复习薄弱点</small></Link><Link href={`/practice?mode=favorites&license=${licenseType}&subject=${subject}`}><span><Heart aria-hidden="true"/></span><strong>收藏题</strong><small>回看重点题目</small></Link><button type="button" onClick={openImagePicker}><span><Camera aria-hidden="true"/></span><strong>拍题提问</strong><small>拍照或选择题图</small></button><button type="button" onClick={() => { setText("我有一道科目一题不理解"); setToolsOpen(false); }}><span><MessageCircleQuestion aria-hidden="true"/></span><strong>AI 讲题</strong><small>换一种方式讲懂</small></button><button type="button" disabled aria-disabled="true"><span><Sparkles aria-hidden="true"/></span><strong>问校长</strong><small>功能暂未开放</small></button></div>}
      <p className="aiDisclaimer">内容由 AI 生成，科目一结论以当前题库依据为准</p>
    </section>
  </div>;
}
