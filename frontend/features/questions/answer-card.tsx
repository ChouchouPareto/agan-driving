"use client";

import { useState } from "react";
import { AlertTriangle, Check, HelpCircle, School } from "lucide-react";
import Link from "next/link";
import { SpecularButton } from "@/components/ui/specular-button";
import type { Answer, Ticket } from "@/lib/schemas/domain";

type Props = { answer: Answer; ticket: Ticket | null; busy: boolean; onFeedback: (type: "resolved" | "not_understood" | "disputed") => void; onTicket: () => void };
type AnswerSection = "reason" | "mistake" | "source";

export function AnswerCard({ answer, ticket, busy, onFeedback, onTicket }: Props) {
  const [section, setSection] = useState<AnswerSection>("reason");
  const tabs: { id: AnswerSection; label: string }[] = [{ id: "reason", label: "原因" }, { id: "mistake", label: "易错" }, { id: "source", label: "来源" }];

  return <>
    <article className="card answer">
      <div className="direct">{answer.direct_answer}</div>
      <p className="reason">{answer.short_reason}</p>
      <section className="answerCarousel" aria-label="答案补充信息" aria-roledescription="carousel">
        <div className="answerCarouselTabs" role="tablist" aria-label="切换答案说明">
          {tabs.map(tab => <button key={tab.id} id={`answer-tab-${tab.id}`} role="tab" aria-selected={section === tab.id} aria-controls={`answer-panel-${tab.id}`} className={section === tab.id ? "active" : ""} onClick={() => setSection(tab.id)}>{tab.label}</button>)}
        </div>
        <div className="answerCarouselViewport">
          <div className="answerCarouselTrack" style={{ transform: `translateX(-${tabs.findIndex(tab => tab.id === section) * 100}%)` }}>
            <div id="answer-panel-reason" className="answerSlide" role="tabpanel" aria-labelledby="answer-tab-reason" aria-hidden={section !== "reason"}><p>{answer.detail}</p></div>
            <div id="answer-panel-mistake" className="answerSlide" role="tabpanel" aria-labelledby="answer-tab-mistake" aria-hidden={section !== "mistake"}><p>{answer.common_mistake}</p></div>
            <div id="answer-panel-source" className="answerSlide sourceSlide" role="tabpanel" aria-labelledby="answer-tab-source" aria-hidden={section !== "source"}>{answer.evidence.length ? answer.evidence.map((item, index) => <div className="evidence" key={`${item.title}-${index}`}><strong>{item.title}</strong><span>{item.version}</span><p>{item.excerpt}</p></div>) : <p>暂时没有命中经过审核的依据，建议提交给校长核查。</p>}</div>
          </div>
        </div>
      </section>
      <div className="actions answerActions">
        <SpecularButton className="resolvedAction" tone="blue" disabled={busy} onClick={() => onFeedback("resolved")}><Check aria-hidden="true" size={18}/>已解决</SpecularButton>
        <SpecularButton className="minorAction" aria-label="还不懂" title="还不懂" disabled={busy} onClick={() => onFeedback("not_understood")}><HelpCircle aria-hidden="true" size={18}/><span className="minorActionText">还不懂</span></SpecularButton>
        <SpecularButton className="minorAction" aria-label="答案有问题" title="答案有问题" disabled={busy} onClick={() => onFeedback("disputed")}><AlertTriangle aria-hidden="true" size={18}/><span className="minorActionText">有问题</span></SpecularButton>
        {answer.risk_codes.length > 0 && <SpecularButton tone="ink" disabled={busy} onClick={onTicket}><School aria-hidden="true" size={18}/>提交给校长</SpecularButton>}
      </div>
    </article>
    {ticket && <section className="card ticket" aria-live="polite"><div className="ticketTitle">{ticket.label}</div><p>{ticket.sla}</p><Link className="textLink" href={`/tickets/${ticket.id}`}>查看处理详情 →</Link></section>}
  </>;
}
