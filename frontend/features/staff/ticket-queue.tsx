"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ticketListSchema, type Ticket } from "@/lib/schemas/domain";
const filters = [{ value: "", label: "全部" }, { value: "QUEUED", label: "待认领" }, { value: "PROCESSING", label: "处理中" }, { value: "REPLIED", label: "待学员确认" }, { value: "CLOSED", label: "已完成" }];
export function TicketQueue() {
  const router = useRouter();
  const [status, setStatus] = useState(""); const [items, setItems] = useState<Ticket[]>([]); const [error, setError] = useState(""); const [busy, setBusy] = useState(true);
  const load = useCallback(async () => { setBusy(true); setError(""); try { const response = await fetch(`/api/staff-backend/staff/review-tickets${status ? `?status=${status}` : ""}`, { cache: "no-store" }); if (response.status === 401) { router.replace("/staff/enter"); return; } const body = await response.json(); if (!response.ok) throw new Error(body.error?.message ?? "加载失败"); setItems(ticketListSchema.parse(body).items); } catch (reason) { setError(reason instanceof Error ? reason.message : "加载失败"); } finally { setBusy(false); } }, [status, router]);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- fetching the selected queue is the external synchronization performed by this effect.
  useEffect(() => { void load(); }, [load]);
  return <><section className="hero"><h1>不懂就问校长</h1><p>优先处理待认领与高风险问题，所有回复都会展示给学员。</p></section><nav className="filterBar" aria-label="工单筛选">{filters.map(item => <button key={item.value} className={`filterChip ${status === item.value ? "active" : ""}`} onClick={() => setStatus(item.value)}>{item.label}</button>)}</nav>{busy && <div className="card status"><span className="dot"/>正在加载工单…</div>}{error && <div className="card error">{error}<button className="button secondaryButton" onClick={load}>重试</button></div>}{!busy && !error && items.length === 0 && <div className="card emptyState">当前筛选下没有工单。</div>}<div className="ticketGrid">{items.map(ticket => <Link className="card queueCard" href={`/staff/tickets/${ticket.id}`} key={ticket.id}><div><span className={`statusPill status-${ticket.status.toLowerCase()}`}>{ticket.label}</span><span className="queueTime">{ticket.updated_at ? new Date(ticket.updated_at).toLocaleString("zh-CN") : ""}</span></div><h2>{ticket.risk_codes.length ? ticket.risk_codes.join(" · ") : "学员主动咨询"}</h2><p>{ticket.sla}</p><span className="textLink">查看并处理 →</span></Link>)}</div></>;
}
