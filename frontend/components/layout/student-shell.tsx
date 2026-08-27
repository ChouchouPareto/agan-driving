"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { BookOpenCheck, Heart, History, Menu, MessageSquarePlus, Search, Settings, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { Brand } from "./brand";
import { hasCurrentContent, learningStage, LICENSE_CATEGORIES, licenseCategory } from "@/lib/learning-catalog";

export function StudentShell({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const selectedLicense = searchParams.get("license") ?? "C1";
  const selectedSubject = searchParams.get("subject") ?? "subject-1";
  const currentLicense = licenseCategory(selectedLicense);
  const currentStage = learningStage(selectedLicense, selectedSubject);
  const contextQuery = `license=${currentLicense.code}&subject=${currentStage.id}`;

  async function updateLearningContext(license: string, subject: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("license", license); params.set("subject", subject);
    await fetch("/api/backend/me/learning-context", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ license_type: license, subject }) }).catch(() => undefined);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  function selectLicense(code: string) {
    const category = licenseCategory(code);
    void updateLearningContext(code, category.stages[0].id);
  }

  function startConversation() {
    sessionStorage.removeItem("super-driving-conversation");
    sessionStorage.removeItem("super-driving-draft");
    setDrawerOpen(false);
    router.push(`/ask?new=1&${contextQuery}`);
  }

  return <div className="shell">
    <header className="topbar">
      <button className="topbarIcon" type="button" aria-label="打开导航" aria-expanded={drawerOpen} onClick={() => setDrawerOpen(true)}><Menu aria-hidden="true"/></button>
      <Brand/>
      <Link className="topbarIcon" href={`/practice?${contextQuery}`} aria-label="进入刷题"><BookOpenCheck aria-hidden="true"/></Link>
    </header>
    <main className="main">{children}</main>
    <div className={`drawerLayer ${drawerOpen ? "open" : ""}`} aria-hidden={!drawerOpen}>
      <button className="drawerScrim" type="button" aria-label="关闭导航" tabIndex={drawerOpen ? 0 : -1} onClick={() => setDrawerOpen(false)}/>
      <aside className="appDrawer" aria-label="超级陪驾导航">
        <div className="drawerHeader"><Brand/><div><button className="drawerIcon" type="button" aria-label="搜索对话"><Search aria-hidden="true"/></button><button className="drawerIcon" type="button" aria-label="关闭导航" onClick={() => setDrawerOpen(false)}><X aria-hidden="true"/></button></div></div>
        <button className="newConversation" type="button" onClick={startConversation}><MessageSquarePlus aria-hidden="true"/><span>新建对话</span></button>
        <nav className="drawerNav" onClick={() => setDrawerOpen(false)}>
          <Link href={`/ask?${contextQuery}`}><Sparkles aria-hidden="true"/><span>与超级陪驾对话</span></Link>
          <Link href={`/practice?${contextQuery}`}><BookOpenCheck aria-hidden="true"/><span>顺序刷题</span></Link>
          <Link href={`/practice?mode=wrong&${contextQuery}`}><History aria-hidden="true"/><span>错题本</span></Link>
          <Link href={`/practice?mode=favorites&${contextQuery}`}><Heart aria-hidden="true"/><span>收藏题</span></Link>
        </nav>
        <section className="learningSelector" aria-label="准驾车型与学习阶段">
          <div className="selectorHeading"><span>学习类目</span><small>{currentLicense.code} · {currentStage.shortLabel}</small></div>
          <label className="licenseSelectLabel" htmlFor="license-category">准驾车型</label>
          <select id="license-category" value={currentLicense.code} onChange={event => selectLicense(event.target.value)}>
            {Array.from(new Set(LICENSE_CATEGORIES.map(item => item.group))).map(group => <optgroup key={group} label={group}>{LICENSE_CATEGORIES.filter(item => item.group === group).map(item => <option key={item.code} value={item.code}>{item.code} · {item.name}</option>)}</optgroup>)}
          </select>
          <div className="stageSelector" role="group" aria-label={`${currentLicense.code} 学习阶段`}>
            {currentLicense.stages.map(stage => <button key={stage.id} type="button" className={stage.id === currentStage.id ? "active" : ""} aria-pressed={stage.id === currentStage.id} onClick={() => void updateLearningContext(currentLicense.code, stage.id)}><strong>{stage.shortLabel}</strong><span>{stage.label.split(" · ")[1] ?? "学习阶段"}</span></button>)}
          </div>
          <p className={`catalogAvailability ${hasCurrentContent(currentLicense.code, currentStage.id) ? "available" : ""}`}>{hasCurrentContent(currentLicense.code, currentStage.id) ? `${currentLicense.code} ${currentStage.shortLabel} 当前可用` : "分类框架已就绪，学习内容暂未开放"}</p>
        </section>
        <div className="drawerAccount"><span className="accountAvatar">{currentLicense.code}</span><div><strong>{currentStage.shortLabel}学员</strong><small>{currentLicense.name}</small></div><button className="drawerIcon" type="button" aria-label="设置"><Settings aria-hidden="true"/></button></div>
      </aside>
    </div>
  </div>;
}
