import Link from "next/link";
import { Brand } from "./brand";
export function StaffShell({ children }: { children: React.ReactNode }) { return <div className="shell"><header className="topbar"><Brand/><nav><Link className="textLink" href="/staff/tickets">工单队列</Link></nav></header><main className="staffMain">{children}</main></div>; }
