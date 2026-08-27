"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Heart, MessageCircleQuestion, RotateCcw } from "lucide-react";
import { z } from "zod";
import { hasCurrentContent, learningStage, licenseCategory } from "@/lib/learning-catalog";

const summarySchema = z.object({ attempted: z.number(), correct_attempts: z.number(), total_attempts: z.number(), wrong_count: z.number(), favorite_count: z.number(), accuracy: z.number() });
const questionSchema = z.object({ id: z.string(), external_id: z.string(), stem: z.string(), options: z.array(z.object({ label: z.string(), text: z.string() })), attempted: z.boolean(), last_correct: z.boolean().nullable(), is_favorite: z.boolean() });
const responseSchema = z.object({ knowledge_version: z.string().nullable(), summary: summarySchema, items: z.array(questionSchema) });
const resultSchema = z.object({ correct: z.boolean(), standard_answer: z.string(), explanation: z.string(), is_favorite: z.boolean(), summary: summarySchema });
type Mode = "all" | "wrong" | "favorites";

export function PracticeWorkspace({ initialMode = "all", license = "C1", subject = "subject-1" }: { initialMode?: Mode; license?: string; subject?: string }) {
  const [items, setItems] = useState<z.infer<typeof questionSchema>[]>([]);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState("");
  const [result, setResult] = useState<z.infer<typeof resultSchema> | null>(null);
  const [error, setError] = useState("");
  const [version, setVersion] = useState("");
  const [summary, setSummary] = useState<z.infer<typeof summarySchema> | null>(null);
  const [mode, setMode] = useState<Mode>(initialMode);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const category = licenseCategory(license);
  const stage = learningStage(license, subject);
  const contentAvailable = hasCurrentContent(category.code, stage.id);

  const load = useCallback(async (nextMode: Mode) => {
    try {
      const query = new URLSearchParams({ mode: nextMode, license_type: category.code, subject: stage.id });
      const response = await fetch(`/api/backend/practice/questions?${query}`, { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error?.message ?? "加载失败");
      const parsed = responseSchema.parse(body);
      setItems(parsed.items); setVersion(parsed.knowledge_version ?? ""); setSummary(parsed.summary);
      setIndex(0); setSelected(""); setResult(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "加载失败"); }
    finally { setLoading(false); }
  }, [category.code, stage.id]);

  // eslint-disable-next-line react-hooks/set-state-in-effect -- loading the selected practice queue is the external synchronization performed here.
  useEffect(() => { setLoading(true); void load(mode); }, [load, mode]);
  useEffect(() => () => { if (advanceTimer.current) clearTimeout(advanceTimer.current); }, []);
  const current = items[index];

  function move(next: number) {
    if (advanceTimer.current) clearTimeout(advanceTimer.current);
    setIndex(next); setSelected(""); setResult(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function answer(label: string) {
    if (!current || saving) return;
    setSelected(label); setSaving(true); setError("");
    try {
      const response = await fetch(`/api/backend/practice/questions/${current.id}/answer`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answer: label }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error?.message ?? "提交失败");
      const parsed = resultSchema.parse(body);
      setResult(parsed); setSummary(parsed.summary);
      if (navigator.vibrate) navigator.vibrate(parsed.correct ? 12 : [20, 40, 20]);
      if (parsed.correct) advanceTimer.current = setTimeout(() => move(index < items.length - 1 ? index + 1 : 0), 1100);
    } catch (reason) { setSelected(""); setError(reason instanceof Error ? reason.message : "提交失败"); }
    finally { setSaving(false); }
  }

  async function toggleFavorite() {
    if (!current) return;
    const next = !current.is_favorite;
    setItems(list => list.map(item => item.id === current.id ? { ...item, is_favorite: next } : item));
    try {
      const response = await fetch(`/api/backend/practice/questions/${current.id}/favorite`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_favorite: next }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error?.message ?? "收藏失败");
      setSummary(summarySchema.parse(body.summary));
    } catch (reason) {
      setItems(list => list.map(item => item.id === current.id ? { ...item, is_favorite: !next } : item));
      setError(reason instanceof Error ? reason.message : "收藏失败");
    }
  }

  const emptyMessage = !contentAvailable
    ? `${category.code} ${stage.shortLabel}分类框架已就绪，学习内容暂未开放。`
    : mode === "wrong" ? "暂时没有错题，继续保持。" : mode === "favorites" ? "还没有收藏题目。" : "当前没有已激活的题库。";

  return <>
    <div className="practiceTop"><Link className="backLink" href={`/ask?license=${category.code}&subject=${stage.id}`}>← 返回首页</Link>{current && <span>{index + 1} / {items.length}</span>}</div>
    <section className="hero"><span className="practiceContext">{category.code} · {category.name} · {stage.label}</span><h1>{stage.shortLabel}练习</h1><p>{version ? `题库版本：${version}${category.code === "C2" ? " · 与 C1 共用理论规则" : ""}` : "使用当前已激活题库。"}</p></section>
    {summary && <section className="practiceSummary" aria-label="学习进度"><div><strong>{summary.attempted}</strong><span>已做题</span></div><div><strong>{(summary.accuracy * 100).toFixed(0)}%</strong><span>正确率</span></div><div><strong>{summary.wrong_count}</strong><span>错题</span></div><div><strong>{summary.favorite_count}</strong><span>收藏</span></div></section>}
    <div className="filterBar" role="group" aria-label="练习范围">{([["all", "顺序练习"], ["wrong", "错题本"], ["favorites", "收藏题"]] as const).map(([value, label]) => <button key={value} className={`filterChip ${mode === value ? "active" : ""}`} aria-pressed={mode === value} onClick={() => { setLoading(true); setError(""); setMode(value); }}>{label}</button>)}</div>
    {error && <div className="card error" role="alert">{error}</div>}
    {loading ? <div className="card status"><span className="dot"/>正在加载练习进度…</div> : !current ? <div className="card emptyState">{emptyMessage}</div> : <>
      <section className="card practiceCard"><div className="practiceQuestionMeta"><span className="questionNumber">第 {index + 1} 题</span><button className={`favoriteButton ${current.is_favorite ? "active" : ""}`} aria-label={current.is_favorite ? "取消收藏" : "收藏题目"} aria-pressed={current.is_favorite} onClick={toggleFavorite}><Heart aria-hidden="true" size={20}/><span>{current.is_favorite ? "已收藏" : "收藏"}</span></button></div><h2>{current.stem}</h2><div className="optionList">{current.options.map(option => { const isSelected = selected === option.label; const isAnswer = result && option.label === result.standard_answer; return <button key={option.label} disabled={Boolean(result) || saving} className={`practiceOption ${isAnswer ? "correct" : result && isSelected ? "wrong" : ""}`} onClick={() => answer(option.label)}><span>{option.label}</span><strong>{option.text}</strong>{isAnswer && <CheckCircle2 aria-hidden="true" size={20}/>}</button>; })}</div>{result && <div className={result.correct ? "practiceResult correctResult" : "practiceResult wrongResult"} aria-live="polite"><strong>{result.correct ? "回答正确 · 即将进入下一题" : "回答错误"}</strong><p>正确答案：{result.standard_answer}</p><p>{result.explanation}</p>{!result.correct && <Link className="button askAiButton" href={`/ask?text=${encodeURIComponent(current.stem)}&license=${category.code}&subject=${stage.id}`}><MessageCircleQuestion aria-hidden="true" size={18}/>这题没懂，问 AI</Link>}</div>}</section>
      <div className="practiceActions"><button className="button secondaryButton" disabled={index === 0} onClick={() => move(index - 1)}><ArrowLeft aria-hidden="true" size={18}/>上一题</button>{result ? <button className="button primary" onClick={() => index < items.length - 1 ? move(index + 1) : move(0)}>{index < items.length - 1 ? <><span>立即下一题</span><ArrowRight aria-hidden="true" size={18}/></> : <><RotateCcw aria-hidden="true" size={18}/><span>重新开始</span></>}</button> : <span className="practiceHint">{saving ? "正在保存进度…" : "请选择答案"}</span>}</div>
    </>}
  </>;
}
