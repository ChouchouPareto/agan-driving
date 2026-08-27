"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { ImageUp, LoaderCircle, RotateCcw } from "lucide-react";
import Image from "next/image";
import * as api from "./api";
import type { OCRTask } from "./schemas";

const MAX_BYTES = 10 * 1024 * 1024;
const TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

type Props = {
  initialTaskId: string;
  onTaskCreated: (taskId: string) => void;
  onQuestionCreated: (questionId: string) => void;
};

export function OCRWorkspace({ initialTaskId, onTaskCreated, onQuestionCreated }: Props) {
  const [task, setTask] = useState<OCRTask | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const preview = task?.preview_url ?? "";

  useEffect(() => {
    if (!initialTaskId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      try {
        const next = await api.getOCRTask(initialTaskId);
        if (!active) return;
        setTask(next);
        setValues(Object.fromEntries(next.fields.map((field) => [field.id, field.value])));
        if (["QUEUED", "PROCESSING"].includes(next.status)) timer = setTimeout(load, 900);
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "识别任务恢复失败");
      }
    };
    load();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [initialTaskId]);

  async function choose(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError("");
    if (!TYPES.has(file.type)) { setError("仅支持 JPEG、PNG 或 WebP 图片。"); return; }
    if (file.size > MAX_BYTES) { setError("图片不能超过 10MB。"); return; }
    setBusy(true); setMessage("正在安全上传图片…"); setTask(null);
    try {
      const uploaded = await api.uploadImage(file);
      setMessage("图片已上传，正在创建识别任务…");
      const created = await api.createOCRTask(uploaded.asset_id);
      setTask(created);
      onTaskCreated(created.id);
      setMessage("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "上传失败，请重试");
      setMessage("");
    } finally { setBusy(false); }
  }

  async function saveAndConfirm() {
    if (!task) return;
    setBusy(true); setError(""); setMessage("正在保存你确认的题目…");
    try {
      const saved = await api.saveOCRFields(task, values);
      setTask(saved);
      const result = await api.confirmOCRTask(saved.id);
      setTask({ ...saved, status: result.status, linked_question_id: result.question_id });
      setMessage("题目已确认，正在进入可信答疑…");
      onQuestionCreated(result.question_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "确认失败，请重试");
      setMessage("");
    } finally { setBusy(false); }
  }

  const statusText = useMemo(() => {
    if (!task) return "";
    if (task.status === "QUEUED") return "已进入识别队列";
    if (task.status === "PROCESSING") return "正在识别题目";
    if (task.status === "WAITING_USER") return "请确认识别内容";
    if (task.status === "FAILED") return task.safe_error?.message ?? "识别失败";
    if (task.status === "QUESTION_CREATED") return "题目已确认";
    return "正在确认任务状态";
  }, [task]);

  return <section className={task ? "ocrPanel active" : "ocrPanel"} aria-label="图片提问">
    {!task && <div className="ocrUploadRow"><label className="uploadButton">
      {busy ? <LoaderCircle className="spin" aria-hidden="true" size={20}/> : <ImageUp aria-hidden="true" size={20}/>}
      {busy ? "正在上传" : "上传题目图片"}
      <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={choose} disabled={busy}/>
    </label><span className="uploadMeta">支持拍照或从相册选择</span></div>}
    {task && <div className="ocrStatus" aria-live="polite"><span className="dot"/>{statusText}</div>}
    {preview && <Image className="ocrPreview" src={preview} width={680} height={360} unoptimized alt="待识别的题目预览"/>}
    {task?.status === "WAITING_USER" && <div className="ocrFields">
      {task.fields.map((field) => <label key={field.id} className={field.needs_confirmation ? "ocrField uncertain" : "ocrField"}>
        <span>{field.field_type === "stem" ? "题干" : `选项 ${field.label ?? ""}`}{field.needs_confirmation && <em>需要确认</em>}</span>
        <textarea value={values[field.id] ?? field.value} onChange={(event) => setValues((current) => ({ ...current, [field.id]: event.target.value }))}/>
      </label>)}
      <div className="actions">
        <button className="button primary" type="button" disabled={busy || task.fields.some((field) => !(values[field.id] ?? field.value).trim())} onClick={saveAndConfirm}>确认并提问</button>
        <label className="button secondaryButton"><RotateCcw aria-hidden="true" size={17}/>重新上传<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={choose} disabled={busy}/></label>
      </div>
    </div>}
    {task?.status === "FAILED" && <label className="button secondaryButton"><RotateCcw aria-hidden="true" size={17}/>重新上传<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={choose} disabled={busy}/></label>}
    {message && <p className="statusText" aria-live="polite">{message}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {(task || busy || message || error) && <p className="privacy ocrPrivacy">请只截取题目区域，不要上传身份证、缴费单等敏感信息。</p>}
  </section>;
}
