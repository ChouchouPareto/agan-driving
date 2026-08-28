import { Brand } from "@/components/layout/brand";
import { InvitationForm } from "@/features/auth/invitation-form";
export default function EnterPage() { return <main className="main"><section className="card invite"><Brand/><h1>使用驾校邀请码进入</h1><p className="reason">进入后可以直接和超级驾陪对话，也可以随时说“我要刷题”。</p><InvitationForm/><p className="privacy">请向所在驾校获取邀请码。身份证、财务和缴费信息不会进入问答模型。</p></section></main>; }
