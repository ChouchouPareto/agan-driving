"use client";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, LoaderCircle } from "lucide-react";

export function InvitationForm() {
  const router = useRouter(); const [code, setCode] = useState("INVITE_CODE_REMOVED"); const [error, setError] = useState(""); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState("");
  useEffect(() => {
    localStorage.removeItem("access_token");
    if (sessionStorage.getItem("super-driving-session-expired")) window.setTimeout(() => setNotice("登录已过期，请重新进入。你刚才输入的内容已保留。"), 0);
    sessionStorage.removeItem("super-driving-session-expired");
    fetch("/api/backend/me").then(async response => {
      if (response.ok) router.replace("/ask");
      else await fetch("/api/session", { method: "DELETE" });
    }).catch(() => undefined);
  }, [router]);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try { const response = await fetch("/api/backend/auth/invitations/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error?.message ?? "邀请码无效或已失效。"); router.replace("/ask"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "进入失败"); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit} noValidate>{notice && <p className="sessionNotice" role="status">{notice}</p>}<label className="label" htmlFor="code">邀请码</label><input id="code" className="input" value={code} onChange={e => setCode(e.target.value)} autoComplete="off" minLength={4} maxLength={64} required aria-describedby={error ? "invite-error" : undefined}/><div className="actions"><button className="button primary" type="submit" disabled={busy}>{busy ? <><LoaderCircle aria-hidden="true" className="spin" size={18}/>正在验证</> : <>进入服务<ArrowRight aria-hidden="true" size={18}/></>}</button></div>{error && <p id="invite-error" className="error" role="alert">{error}</p>}</form>;
}
