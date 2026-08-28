"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Clock3, RotateCcw } from "lucide-react";
import { z } from "zod";
import { learningStage, licenseCategory } from "@/lib/learning-catalog";

const questionSchema = z.object({ id: z.string(), external_id: z.string(), stem: z.string(), options: z.array(z.object({ label: z.string(), text: z.string() })) });
const examSchema = z.object({ knowledge_version: z.string().nullable(), duration_minutes: z.number(), pass_score: z.number(), items: z.array(questionSchema) });
const resultSchema = z.object({ score: z.number(), passed: z.boolean(), correct_count: z.number(), total: z.number(), details: z.array(z.object({ question_id: z.string(), selected_answer: z.string(), standard_answer: z.string(), correct: z.boolean(), explanation: z.string() })) });

export function MockExamWorkspace({ license = "C1", subject = "subject-1" }: { license?: string; subject?: string }) {
  const category = licenseCategory(license); const stage = learningStage(license, subject);
  const [exam, setExam] = useState<z.infer<typeof examSchema> | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({}); const [index, setIndex] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState(45 * 60); const [result, setResult] = useState<z.infer<typeof resultSchema> | null>(null);
  const [loading, setLoading] = useState(true); const [submitting, setSubmitting] = useState(false); const [error, setError] = useState("");

  const start = useCallback(async () => { setLoading(true); setError(""); setResult(null); setAnswers({}); setIndex(0); try { const query = new URLSearchParams({ license_type: category.code, subject: stage.id }); const response = await fetch(`/api/backend/practice/mock-exam?${query}`, { cache: "no-store" }); const body = await response.json(); if (!response.ok) throw new Error(body.error?.message ?? "加载试卷失败"); const parsed = examSchema.parse(body); setExam(parsed); setSecondsLeft(parsed.duration_minutes * 60); } catch (reason) { setError(reason instanceof Error ? reason.message : "加载试卷失败"); } finally { setLoading(false); } }, [category.code, stage.id]);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- fetching a fresh exam is the external synchronization performed here.
  useEffect(() => { void start(); }, [start]);
  useEffect(() => { if (!exam || result || secondsLeft <= 0) return; const timer = window.setInterval(() => setSecondsLeft(value => Math.max(0, value - 1)), 1000); return () => window.clearInterval(timer); }, [exam, result, secondsLeft]);
  const current = exam?.items[index]; const answeredCount = Object.keys(answers).length;
  const timeText = useMemo(() => `${String(Math.floor(secondsLeft / 60)).padStart(2, "0")}:${String(secondsLeft % 60).padStart(2, "0")}`, [secondsLeft]);

  async function submit() { if (!exam || !exam.items.length || submitting) return; setSubmitting(true); setError(""); try { const query = new URLSearchParams({ license_type: category.code, subject: stage.id }); const response = await fetch(`/api/backend/practice/mock-exam?${query}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers: exam.items.map(item => ({ question_id: item.id, answer: answers[item.id] })) }) }); const body = await response.json(); if (!response.ok) throw new Error(body.error?.message ?? "交卷失败"); setResult(resultSchema.parse(body)); window.scrollTo({ top: 0, behavior: "smooth" }); } catch (reason) { setError(reason instanceof Error ? reason.message : "交卷失败"); } finally { setSubmitting(false); } }

  if (loading) return <div className="card status"><span className="dot"/>正在生成模拟试卷…</div>;
  if (error && !exam) return <div className="card emptyState">{error}<button className="button primary" onClick={() => void start()}>重新加载</button></div>;
  if (!exam?.items.length) return <div className="card emptyState">当前题库暂时无法生成模拟试卷。</div>;
  if (result) return <section className="examResult"><span className={result.passed ? "examPass" : "examRetry"}>{result.passed ? "本次通过" : "继续加油"}</span><strong>{result.score}<small>分</small></strong><h1>{result.passed ? "已经达到模拟通过线" : "离通过线又近了一步"}</h1><p>答对 {result.correct_count} / {result.total} 题。错题已经自动进入错题本，超级陪驾会继续陪你补薄弱点。</p><div className="actions"><Link className="specularLink" href={`/practice?mode=wrong&license=${category.code}&subject=${stage.id}`}>复习本次错题</Link><button className="specularButton specularButton--blue" onClick={() => void start()}><span><RotateCcw size={18}/>再考一次</span></button></div></section>;

  return <><header className="examHeader"><div><Link className="backLink" href={`/practice?license=${category.code}&subject=${stage.id}`}>← 退出模拟考</Link><span>{category.code} · {stage.shortLabel}</span></div><div className="examTimer"><Clock3 size={17}/><strong>{timeText}</strong></div></header><section className="examProgress"><div><span style={{ width: `${answeredCount / exam.items.length * 100}%` }}/></div><p>已答 {answeredCount} / {exam.items.length} · {exam.pass_score} 分及格</p></section>{current && <section className="card practiceCard examCard"><div className="practiceQuestionMeta"><span className="questionNumber">第 {index + 1} 题</span><span className="mode">考试中不显示答案</span></div><h2>{current.stem}</h2><div className="optionList">{current.options.map(option => { const showLabel = option.label.trim() !== option.text.trim(); return <button key={option.label} className={`practiceOption ${answers[current.id] === option.label ? "examSelected" : ""}`} onClick={() => setAnswers(value => ({ ...value, [current.id]: option.label }))}>{showLabel && <span>{option.label}</span>}<strong>{option.text}</strong>{answers[current.id] === option.label && <CheckCircle2 size={19}/>}</button>; })}</div></section>}<div className="examNavigation"><button className="button secondaryButton" disabled={index === 0} onClick={() => setIndex(value => value - 1)}><ArrowLeft size={18}/>上一题</button>{index < exam.items.length - 1 ? <button className="button primary" onClick={() => setIndex(value => value + 1)}>下一题<ArrowRight size={18}/></button> : <button className="button primary" disabled={answeredCount !== exam.items.length || submitting} onClick={() => void submit()}>{submitting ? "正在交卷…" : answeredCount === exam.items.length ? "确认交卷" : `还有 ${exam.items.length - answeredCount} 题`}</button>}</div>{error && <div className="card error">{error}</div>}</>;
}
