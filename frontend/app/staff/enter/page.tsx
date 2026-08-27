import { Brand } from "@/components/layout/brand";
import { StaffEnterForm } from "@/features/staff/staff-enter-form";
export default function Page() { return <main className="main"><section className="card invite"><Brand/><h1>校长工作台</h1><p className="reason">处理需要真人判断的学员问题。员工与学员登录相互独立。</p><StaffEnterForm/><p className="privacy">测试邀请码：INVITE_CODE_REMOVED</p></section></main>; }
