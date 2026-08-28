import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Brand } from "./brand";
export function StaffShell({ children }: { children: React.ReactNode }) { return <div className="shell"><header className="topbar staffTopbar"><Link className="staffHome" href="/ask"><ArrowLeft aria-hidden="true" size={17}/><span>返回学员端</span></Link><Brand/><nav className="staffNav"><Link href="/staff/tickets">工单队列</Link><Link href="/staff/knowledge">题库版本</Link><Link href="/staff/evaluations">离线评测</Link></nav></header><main className="staffMain">{children}</main></div>; }
