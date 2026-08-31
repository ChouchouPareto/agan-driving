"use client";

import { useState } from "react";
import { BookOpenCheck, Check, ChevronRight, Clock3, Layers3, Lightbulb, Play, RotateCcw, VolumeX } from "lucide-react";

const FIRST_MEDIA_SCENARIOS = [
  "无信号路口让行",
  "转弯让直行",
  "环岛进出顺序",
  "人行横道礼让",
  "超车与会车",
  "高速汇入与驶离",
  "安全跟车距离",
  "雨雾天气灯光",
  "爆胎应急处置",
  "车辆故障警示",
  "交通标志辨析",
  "事故现场处置",
] as const;

function IntersectionIllustration({ step }: { step: number }) {
  return <svg className="intersectionIllustration" viewBox="0 0 720 420" role="img" aria-labelledby="intersection-title intersection-description">
    <title id="intersection-title">无信号灯十字路口让行示意图</title>
    <desc id="intersection-description">绿色车辆减速等待，右方黑色车辆先通过路口。</desc>
    <defs>
      <marker id="arrow-green" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#257f6d"/></marker>
      <marker id="arrow-ink" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#191b1a"/></marker>
      <filter id="vehicle-shadow" x="-25%" y="-25%" width="150%" height="170%"><feDropShadow dx="0" dy="8" stdDeviation="8" floodColor="#17201d" floodOpacity=".18"/></filter>
    </defs>
    <rect width="720" height="420" rx="28" fill="#e5eee9"/>
    <path d="M0 0h248v96H0zm472 0h248v96H472zM0 324h248v96H0zm472 324h248v96H472z" fill="#d8e8df"/>
    <circle cx="58" cy="66" r="30" fill="#c2d9cc"/><circle cx="664" cy="350" r="38" fill="#c2d9cc"/><circle cx="84" cy="360" r="22" fill="#cbded3"/>
    <rect x="0" y="132" width="720" height="156" fill="#c9d0cd"/>
    <rect x="282" y="0" width="156" height="420" fill="#c9d0cd"/>
    <path d="M0 210H720M360 0V420" stroke="#f8faf9" strokeWidth="4" strokeDasharray="18 18" opacity=".95"/>
    <path d="M275 132v-34M445 288v34M282 295h-34M438 125h34" stroke="#fff" strokeWidth="8"/>
    <path d="M360 302V232" stroke="#257f6d" strokeWidth="8" strokeLinecap="round" markerEnd="url(#arrow-green)" opacity={step === 1 ? 1 : .24}/>
    <path d="M478 210H392" stroke="#191b1a" strokeWidth="8" strokeLinecap="round" markerEnd="url(#arrow-ink)" opacity={step === 2 ? 1 : .24}/>
    <g className={step === 1 ? "demoVehicle active" : "demoVehicle"} transform="translate(319 310)" filter="url(#vehicle-shadow)"><rect width="82" height="50" rx="15" fill="#257f6d"/><rect x="18" y="7" width="46" height="36" rx="9" fill="#bfe0d7"/><circle cx="17" cy="50" r="7" fill="#191b1a"/><circle cx="65" cy="50" r="7" fill="#191b1a"/></g>
    <g className={step === 2 ? "demoVehicle active" : "demoVehicle"} transform="translate(493 177) rotate(90 41 25)" filter="url(#vehicle-shadow)"><rect width="82" height="50" rx="15" fill="#191b1a"/><rect x="18" y="7" width="46" height="36" rx="9" fill="#d7d9d8"/><circle cx="17" cy="50" r="7" fill="#191b1a"/><circle cx="65" cy="50" r="7" fill="#191b1a"/></g>
    <g transform="translate(286 374)"><rect width="148" height="34" rx="17" fill="#fff"/><circle cx="18" cy="17" r="11" fill="#257f6d"/><text x="18" y="22" textAnchor="middle" fill="#fff" fontSize="13" fontWeight="800">2</text><text x="38" y="22" fill="#17201d" fontSize="15" fontWeight="700">你的车 · 等待</text></g>
    <g transform="translate(516 112)"><rect width="164" height="34" rx="17" fill="#fff"/><circle cx="18" cy="17" r="11" fill="#191b1a"/><text x="18" y="22" textAnchor="middle" fill="#fff" fontSize="13" fontWeight="800">1</text><text x="38" y="22" fill="#17201d" fontSize="15" fontWeight="700">右方来车 · 先行</text></g>
    <g transform="translate(28 26)"><rect width="202" height="50" rx="25" fill="#fff" opacity=".96"/><circle cx="26" cy="25" r="9" fill={step === 1 ? "#257f6d" : "#191b1a"}/><text x="47" y="31" fill="#17201d" fontSize="18" fontWeight="700">{step === 1 ? "第 1 步：减速观察" : "第 2 步：右车先走"}</text></g>
  </svg>;
}

export function MediaLearningDemo() {
  const [mode, setMode] = useState<"image" | "motion">("image");
  const [step, setStep] = useState(1);

  function advance() {
    setMode("motion");
    setStep(value => value === 1 ? 2 : 1);
  }

  return <div className="mediaDemoPage">
    <header className="mediaDemoIntro">
      <span>C1 · 科目一 · 媒体知识卡 V2</span>
      <h1>不是多放一张图，<br/>而是换一种方式讲懂。</h1>
      <p>同一份知识点，可以自然出现在超级驾陪的回答、答题解析和错题复习里。</p>
    </header>

    <section className="mediaDemoChat" aria-label="超级驾陪图文回答示例">
      <div className="mediaDemoUser">没有信号灯的路口，到底该让谁先走？</div>
      <article className="mediaAnswer">
        <div className="mediaAnswerAuthor"><span>驾</span><div><strong>超级驾陪</strong><small>学车伙伴</small></div></div>
        <h2>先减速看清楚，再让右方来车先走。</h2>
        <p>你把自己想成站在路口中间：右手边来的车更不容易看见你，所以先让它过去，会更安全。</p>
        <div className="mediaModeTabs" role="tablist" aria-label="切换讲解方式">
          <button type="button" role="tab" aria-selected={mode === "image"} className={mode === "image" ? "active" : ""} onClick={() => { setMode("image"); setStep(1); }}>看图</button>
          <button type="button" role="tab" aria-selected={mode === "motion"} className={mode === "motion" ? "active" : ""} onClick={() => setMode("motion")}>动态演示</button>
        </div>
        <div className="mediaVisual">
          <IntersectionIllustration step={step}/>
          {mode === "motion" && <button className="mediaPlay" type="button" aria-label="播放下一步动态演示" onClick={advance}><Play aria-hidden="true" fill="currentColor"/></button>}
          <div className="mediaVisualMeta"><span><VolumeX aria-hidden="true"/>默认静音</span><span><Clock3 aria-hidden="true"/>15 秒</span></div>
        </div>
        <div className="mediaTakeaway"><Lightbulb aria-hidden="true"/><div><small>一句记住</small><strong>无灯无标线，右方来车先。</strong></div></div>
        <button className="mediaPracticeLink" type="button"><BookOpenCheck aria-hidden="true"/><span>练一道同类题</span><ChevronRight aria-hidden="true"/></button>
      </article>
    </section>

    <section className="mediaScenarioPlan" aria-labelledby="media-plan-title">
      <div className="mediaScenarioHeading">
        <div><span>首批范围</span><h2 id="media-plan-title">先把 12 个高频场景讲透</h2></div>
        <p><strong>1</strong> 个示例已完成 · <strong>11</strong> 个进入首批开发</p>
      </div>
      <div className="mediaScenarioGrid">
        {FIRST_MEDIA_SCENARIOS.map((scenario, index) => <div className={index === 0 ? "mediaScenario active" : "mediaScenario"} key={scenario}>
          <span>{String(index + 1).padStart(2, "0")}</span>
          <strong>{scenario}</strong>
          {index === 0 && <small>当前示例</small>}
        </div>)}
      </div>
      <div className="mediaExpansionRule"><Layers3 aria-hidden="true"/><p><strong>后续不盲目铺量。</strong>根据真实咨询量、错题率和“还不懂”反馈，优先补充最值得做成图片或短视频的知识点。</p></div>
    </section>

    <section className="wrongReviewDemo" aria-label="错题复习示例">
      <div className="wrongReviewHeading"><div><span>错题复习</span><h2>这次换张图记</h2></div><strong>1 / 3</strong></div>
      <div className="wrongReviewCard">
        <div className="wrongReviewThumb"><IntersectionIllustration step={2}/></div>
        <div className="wrongReviewCopy"><span><Check aria-hidden="true"/>已找到你的易错点</span><h3>你记住了“减速”，但漏掉了“让右方先行”。</h3><p>先看车从哪边来，再决定谁先走。</p></div>
        <button type="button"><RotateCcw aria-hidden="true"/>重新做题</button>
      </div>
    </section>
  </div>;
}
