"use client";

import { useCallback, useEffect, useState } from "react";
import { BackButton } from "@/components/ui/back-button";
import { ticketSchema, type Ticket } from "@/lib/schemas/domain";

export function StudentTicketDetail({ id }: { id: string }) {
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch(`/api/backend/review-tickets/${id}`, { cache: "no-store" });
    const body = await response.json();
    if (!response.ok) {
      setError(body.error?.message ?? "加载失败");
      return;
    }
    setTicket(ticketSchema.parse(body));
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial ticket data is loaded from the backend here.
    void load();
  }, [load]);

  async function acknowledge() {
    if (!ticket) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`/api/backend/review-tickets/${id}/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ version: ticket.version }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error?.message ?? "操作失败");
      setTicket(ticketSchema.parse(body));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  if (!ticket) return <div className="card status">{error || "正在加载处理进度…"}</div>;

  return (
    <>
      <BackButton href="/ask" label="返回答疑" />
      <section className="hero">
        <span className={`statusPill status-${ticket.status.toLowerCase()}`}>{ticket.label}</span>
        <h1>校长处理进度</h1>
        <p>{ticket.sla}</p>
      </section>
      {error && <div className="card error">{error}</div>}
      <section className="card">
        <h2>我的问题</h2>
        <p className="questionText">{ticket.question?.text}</p>
      </section>
      <section className="card">
        <h2>处理记录</h2>
        <ol className="timeline">
          {ticket.events.map((event) => (
            <li key={event.id}>
              <strong>{event.event_type === "CLAIMED" ? "校长开始处理" : event.event_type === "REPLIED" ? "校长已回复" : "你已确认解决"}</strong>
              <span>{new Date(event.created_at).toLocaleString("zh-CN")}</span>
            </li>
          ))}
        </ol>
        {ticket.events.length === 0 && <p className="reason">已进入队列，等待校长认领。</p>}
      </section>
      {ticket.messages.map((message) => (
        <section className="card ticket" key={message.id}>
          <div className="ticketTitle">校长回复</div>
          <p className="questionText">{message.content}</p>
        </section>
      ))}
      {ticket.status === "REPLIED" && (
        <section className="card">
          <h2>这个问题解决了吗？</h2>
          <p className="reason">确认后工单将结束；如果还没解决，可以先保留等待后续处理。</p>
          <button className="button primary" disabled={busy} onClick={acknowledge}>
            {busy ? "正在确认…" : "确认已解决"}
          </button>
        </section>
      )}
    </>
  );
}
