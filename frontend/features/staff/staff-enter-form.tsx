"use client";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
export function StaffEnterForm() {
  const router = useRouter(); const [code, setCode] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); setError(""); try { const response = await fetch("/api/staff-backend/staff/auth/invitations/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }); const body = await response.json(); if (!response.ok) throw new Error(body.error?.message ?? "进入失败"); router.replace("/staff/tickets"); } catch (reason) { setError(reason instanceof Error ? reason.message : "进入失败"); } finally { setBusy(false); } }
  return <form onSubmit={submit}><label className="label" htmlFor="staff-code">工作台邀请码</label><input id="staff-code" className="input" value={code} onChange={e => setCode(e.target.value)} required/><div className="actions"><button className="button primary" disabled={busy}>{busy ? "正在验证…" : "进入校长工作台"}</button></div>{error && <p className="error" role="alert">{error}</p>}</form>;
}
