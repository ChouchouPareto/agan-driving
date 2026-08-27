import { Brand } from "./brand";
export function StudentShell({ children }: { children: React.ReactNode }) { return <div className="shell"><header className="topbar"><Brand/><span className="mode">科目一 AI 陪练</span></header><main className="main">{children}</main></div>; }
