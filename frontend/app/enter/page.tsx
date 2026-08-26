import { Brand } from "@/components/layout/brand";
import { InvitationForm } from "@/features/auth/invitation-form";
export default function EnterPage() { return <main className="main"><section className="card invite"><Brand/><h1>使用驾校邀请码进入</h1><p className="reason">前期测试入口，只收集完成答疑所需的最少信息。</p><InvitationForm/><p className="privacy">测试邀请码：INVITE_CODE_REMOVED。身份证、财务和缴费信息不会进入问答模型。</p></section></main>; }
