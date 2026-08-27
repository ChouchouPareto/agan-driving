"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { BookOpenCheck, Heart, History, Menu, MessageSquarePlus, Search, Settings, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { Brand } from "./brand";

export function StudentShell({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const router = useRouter();

  function startConversation() {
    sessionStorage.removeItem("super-driving-conversation");
    sessionStorage.removeItem("super-driving-draft");
    setDrawerOpen(false);
    router.push("/ask?new=1");
  }

  return <div className="shell">
    <header className="topbar">
      <button className="topbarIcon" type="button" aria-label="打开导航" aria-expanded={drawerOpen} onClick={() => setDrawerOpen(true)}><Menu aria-hidden="true"/></button>
      <Brand/>
      <Link className="topbarIcon" href="/practice" aria-label="进入刷题"><BookOpenCheck aria-hidden="true"/></Link>
    </header>
    <main className="main">{children}</main>
    <div className={`drawerLayer ${drawerOpen ? "open" : ""}`} aria-hidden={!drawerOpen}>
      <button className="drawerScrim" type="button" aria-label="关闭导航" tabIndex={drawerOpen ? 0 : -1} onClick={() => setDrawerOpen(false)}/>
      <aside className="appDrawer" aria-label="超级陪驾导航">
        <div className="drawerHeader"><Brand/><div><button className="drawerIcon" type="button" aria-label="搜索对话"><Search aria-hidden="true"/></button><button className="drawerIcon" type="button" aria-label="关闭导航" onClick={() => setDrawerOpen(false)}><X aria-hidden="true"/></button></div></div>
        <button className="newConversation" type="button" onClick={startConversation}><MessageSquarePlus aria-hidden="true"/><span>新建对话</span></button>
        <nav className="drawerNav" onClick={() => setDrawerOpen(false)}>
          <Link href="/ask"><Sparkles aria-hidden="true"/><span>与超级陪驾对话</span></Link>
          <Link href="/practice"><BookOpenCheck aria-hidden="true"/><span>顺序刷题</span></Link>
          <Link href="/practice?mode=wrong"><History aria-hidden="true"/><span>错题本</span></Link>
          <Link href="/practice?mode=favorites"><Heart aria-hidden="true"/><span>收藏题</span></Link>
        </nav>
        <div className="drawerEmpty"><span>更早</span><p>暂无更多学习记录</p></div>
        <div className="drawerAccount"><span className="accountAvatar">C1</span><div><strong>科目一学员</strong><small>超级陪驾学习版</small></div><button className="drawerIcon" type="button" aria-label="设置"><Settings aria-hidden="true"/></button></div>
      </aside>
    </div>
  </div>;
}
