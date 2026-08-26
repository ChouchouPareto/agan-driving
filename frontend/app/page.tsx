"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
type Evidence = { title: string; version: string; excerpt: string };
type Answer = { id: string; direct_answer: string; short_reason: string; detail: string; common_mistake: string; evidence: Evidence[]; risk_codes: string[] };
type Ticket = { id: string; status: string; label: string; sla: string };

async function api(path: string, options: RequestInit = {}) {
  const token = localStorage.getItem("access_token");
  const response = await fetch(`${API}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message ?? data.detail?.message ?? "请求失败");
  return data;
}

export default function Home() {
  const [ready, setReady] = useState(false);
  const [code, setCode] = useState("INVITE_CODE_REMOVED");
  const [conversationId, setConversationId] = useState("");
  const [questionId, setQuestionId] = useState("");
  const [text, setText] = useState("驾驶机动车通过没有交通信号的交叉路口怎样行驶？");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const frame = requestAnimationFrame(() => setReady(Boolean(localStorage.getItem("access_token"))));
    return () => cancelAnimationFrame(frame);
  }, []);

  async function enter(e: FormEvent) {
    e.preventDefault(); setError("");
    try { const result = await api("/auth/invitations/verify", { method: "POST", body: JSON.stringify({ code }) }); localStorage.setItem("access_token", result.access_token); setReady(true); }
    catch (err) { setError(err instanceof Error ? err.message : "进入失败"); }
  }

  async function ask(e: FormEvent) {
    e.preventDefault(); setError(""); setAnswer(null); setTicket(null); setStatus("正在准备问题…");
    try {
      let cid = conversationId;
      if (!cid) { const conversation = await api("/conversations", { method: "POST", body: "{}" }); cid = conversation.id; setConversationId(cid); }
      const question = await api("/questions", { method: "POST", body: JSON.stringify({ conversation_id: cid, text }) });
      setQuestionId(question.id); setStatus("正在查找可信依据…");
      const response = await fetch(`${API}/questions/${question.id}/stream`, { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } });
      if (!response.ok || !response.body) throw new Error("回答服务暂时不可用");
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
      while (true) {
        const { done, value } = await reader.read(); if (done) break; buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n"); buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const event = frame.match(/event: (.+)/)?.[1]; const raw = frame.match(/data: (.+)/)?.[1]; if (!raw) continue;
          const data = JSON.parse(raw);
          if (event === "status") setStatus("正在组织答案并检查一致性…");
          if (event === "done") { setAnswer(data); setStatus(""); }
          if (event === "error") throw new Error(data.error?.message ?? "回答失败");
        }
      }
    } catch (err) { setStatus(""); setError(err instanceof Error ? err.message : "提问失败"); }
  }

  async function feedback(type: "resolved" | "not_understood" | "disputed") {
    if (!answer) return;
    try {
      await api(`/answers/${answer.id}/feedback`, { method: "POST", body: JSON.stringify({ type }) });
      if (type === "resolved") setStatus("已记录：这个问题解决了。");
      else if (type === "not_understood") { setStatus("正在换一种方式解释…"); const next = await api(`/answers/${answer.id}/explain-again`, { method: "POST" }); setAnswer(next); setStatus(""); }
      else await createTicket(["USER_DISPUTE"]);
    } catch (err) { setError(err instanceof Error ? err.message : "操作失败"); }
  }

  async function createTicket(riskCodes = answer?.risk_codes ?? []) {
    if (!questionId) return;
    const created = await api("/review-tickets", { method: "POST", body: JSON.stringify({ question_id: questionId, risk_codes: riskCodes }) });
    const current = await api(`/review-tickets/${created.id}`); setTicket(current);
  }

  if (!ready) return <main className="main"><section className="card invite"><div className="brand"><span className="brandMark">问</span>科目一智能助教</div><h1>使用驾校邀请码进入</h1><p className="reason">首阶段测试入口，只收集完成答疑所需的最少信息。</p><form onSubmit={enter}><label className="label" htmlFor="code">邀请码</label><input id="code" className="input" value={code} onChange={e => setCode(e.target.value)} autoComplete="off"/><div className="actions"><button className="button primary" type="submit">进入服务</button></div></form>{error && <p className="error" role="alert">{error}</p>}<p className="privacy">测试邀请码：INVITE_CODE_REMOVED。身份证、财务和缴费信息不会进入问答模型。</p></section></main>;

  return <div className="shell"><header className="topbar"><div className="brand"><span className="brandMark">问</span>科目一智能助教</div><span className="mode">第一阶段测试</span></header><main className="main"><section className="hero"><h1>今天有什么没看懂？</h1><p>先给结论，再讲原因；没有可靠依据时不会猜。</p></section><form className="card" onSubmit={ask}><label className="label" htmlFor="question">输入题目或科目一问题</label><textarea id="question" className="input" value={text} onChange={e => setText(e.target.value)} maxLength={2000}/><div className="actions"><button className="button primary" type="submit" disabled={Boolean(status)}>提交问题</button></div></form>{status && <div className="card status" aria-live="polite"><span className="dot"/>{status}</div>}{error && <div className="card error" role="alert">{error}</div>}{answer && <article className="card answer"><span className="mode">可信回答</span><div className="direct">{answer.direct_answer}</div><p className="reason">{answer.short_reason}</p><details open><summary>为什么这样判断</summary><p className="detailText">{answer.detail}</p></details><details><summary>易错提醒</summary><p className="detailText">{answer.common_mistake}</p></details><details><summary>查看依据</summary>{answer.evidence.length ? answer.evidence.map((item, i) => <div className="evidence" key={i}><strong>{item.title}</strong> · {item.version}<br/>{item.excerpt}</div>) : <p className="detailText">暂时没有命中经过审核的依据，建议提交给校长核查。</p>}</details><div className="actions"><button className="button primary" onClick={() => feedback("resolved")}>已解决</button><button className="button secondaryButton" onClick={() => feedback("not_understood")}>还不懂</button><button className="button dangerButton" onClick={() => feedback("disputed")}>答案有问题</button>{answer.risk_codes.length > 0 && <button className="button secondaryButton" onClick={() => createTicket()}>提交给校长</button>}</div></article>}{ticket && <section className="card ticket" aria-live="polite"><div className="ticketTitle">{ticket.label}</div><p>{ticket.sla}</p></section>}</main></div>;
}
