"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { z } from "zod";
const versionSchema = z.object({ id: z.string(), version_label: z.string(), status: z.string(), region: z.string(), license_type: z.string(), item_count: z.number(), error_count: z.number(), embedding_model: z.string(), collection_name: z.string().nullable(), created_at: z.string() });
const listSchema = z.object({ items: z.array(versionSchema) });
export function KnowledgeList() {
  const [items, setItems] = useState<z.infer<typeof versionSchema>[]>([]); const [error, setError] = useState("");
  useEffect(() => { fetch("/api/staff-backend/staff/knowledge/versions", { cache: "no-store" }).then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.error?.message ?? "加载失败"); setItems(listSchema.parse(body).items); }).catch(reason => setError(reason instanceof Error ? reason.message : "加载失败")); }, []);
  return <><section className="hero"><h1>题库版本</h1><p>题库通过机器校验和索引门禁后生效；异常版本不会进入学员检索。</p></section>{error && <div className="card error">{error}</div>}{!error && items.length === 0 && <div className="card emptyState">尚未导入题库。第一版请使用受控命令行导入。</div>}<div className="ticketGrid">{items.map(item => <Link className="card queueCard" href={`/staff/knowledge/${item.id}`} key={item.id}><div><span className={`statusPill ${item.status === "ACTIVE" ? "status-closed" : item.status === "BLOCKED" ? "status-replied" : "status-processing"}`}>{item.status}</span><span className="queueTime">{new Date(item.created_at).toLocaleString("zh-CN")}</span></div><h2>{item.version_label}</h2><p>{item.region} · {item.license_type} · {item.item_count} 题 · {item.error_count} 个异常</p><span className="textLink">查看版本 →</span></Link>)}</div></>;
}
