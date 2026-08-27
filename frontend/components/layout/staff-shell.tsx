import Link from "next/link";
import { Brand } from "./brand";
export function StaffShell({ children }: { children: React.ReactNode }) { return <div className="shell"><header className="topbar"><Brand/><nav className="staffNav"><Link className="textLink" href="/staff/tickets">工单队列</Link><Link className="textLink" href="/staff/knowledge">题库版本</Link></nav></header><main className="staffMain">{children}</main></div>; }
