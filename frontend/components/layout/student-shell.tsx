"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { BookOpenCheck, Check, Heart, History, Menu, MessageSquarePlus, Pencil, Search, Settings, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { Brand } from "./brand";
import { learningStage, LICENSE_CATEGORIES, licenseCategory } from "@/lib/learning-catalog";

export function StudentShell({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
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
    setPickerOpen(false);
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
      <button className="drawerScrim" type="button" aria-label="关闭导航" tabIndex={drawerOpen ? 0 : -1} onClick={() => { setDrawerOpen(false); setPickerOpen(false); }}/>
      <aside className="appDrawer" aria-label="超级陪驾导航">
        <div className="drawerHeader"><Brand/><div><button className="drawerIcon" type="button" aria-label="搜索对话"><Search aria-hidden="true"/></button><button className="drawerIcon" type="button" aria-label="关闭导航" onClick={() => { setDrawerOpen(false); setPickerOpen(false); }}><X aria-hidden="true"/></button></div></div>
        <button className="newConversation" type="button" onClick={startConversation}><MessageSquarePlus aria-hidden="true"/><span>新建对话</span></button>
        <nav className="drawerNav" onClick={() => setDrawerOpen(false)}>
          <Link href={`/ask?${contextQuery}`}><Sparkles aria-hidden="true"/><span>与超级陪驾对话</span></Link>
          <Link href={`/practice?${contextQuery}`}><BookOpenCheck aria-hidden="true"/><span>顺序刷题</span></Link>
          <Link href={`/practice?mode=wrong&${contextQuery}`}><History aria-hidden="true"/><span>错题本</span></Link>
          <Link href={`/practice?mode=favorites&${contextQuery}`}><Heart aria-hidden="true"/><span>收藏题</span></Link>
        </nav>
        <section className="learningSelector" aria-label="准驾车型与学习阶段">
          <div className="compactLearningHeader"><div><small>当前学习</small><strong>{currentLicense.code} · {currentLicense.name}</strong></div><button type="button" aria-label="修改准驾车型" aria-expanded={pickerOpen} onClick={() => setPickerOpen(value => !value)}><Pencil aria-hidden="true"/><span>修改</span></button></div>
          <div className="stageSelector" role="group" aria-label={`${currentLicense.code} 学习阶段`}>
            {currentLicense.stages.map(stage => <button key={stage.id} type="button" className={stage.id === currentStage.id ? "active" : ""} aria-pressed={stage.id === currentStage.id} onClick={() => void updateLearningContext(currentLicense.code, stage.id)}>{stage.shortLabel}</button>)}
          </div>
          {pickerOpen && <div className="licensePicker" aria-label="选择准驾车型"><div className="licensePickerHeader"><strong>选择准驾车型</strong><button type="button" aria-label="关闭车型选择" onClick={() => setPickerOpen(false)}><X aria-hidden="true"/></button></div>{Array.from(new Set(LICENSE_CATEGORIES.map(item => item.group))).map(group => <section key={group}><h3>{group}</h3>{LICENSE_CATEGORIES.filter(item => item.group === group).map(item => <button key={item.code} type="button" className={item.code === currentLicense.code ? "selected" : ""} aria-pressed={item.code === currentLicense.code} onClick={() => selectLicense(item.code)}><span>{item.code} · {item.name}</span>{item.code === currentLicense.code && <Check aria-hidden="true"/>}</button>)}</section>)}</div>}
        </section>
        <div className="drawerAccount"><span className="accountAvatar">{currentLicense.code}</span><div><strong>{currentStage.shortLabel}学员</strong><small>{currentLicense.name}</small></div><button className="drawerIcon" type="button" aria-label="设置"><Settings aria-hidden="true"/></button></div>
      </aside>
    </div>
  </div>;
}
