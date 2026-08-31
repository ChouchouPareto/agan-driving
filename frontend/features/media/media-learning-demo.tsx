"use client";

import { useState } from "react";
import { BookOpenCheck, Check, ChevronRight, Clock3, Lightbulb, Play, RotateCcw, VolumeX } from "lucide-react";

function IntersectionIllustration({ step }: { step: number }) {
  return <svg className="intersectionIllustration" viewBox="0 0 720 420" role="img" aria-labelledby="intersection-title intersection-description">
    <title id="intersection-title">无信号灯十字路口让行示意图</title>
    <desc id="intersection-description">绿色车辆减速等待，右方黑色车辆先通过路口。</desc>
    <defs>
      <marker id="arrow-green" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#257f6d"/></marker>
      <marker id="arrow-ink" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#191b1a"/></marker>
    </defs>
    <rect width="720" height="420" rx="28" fill="#edf2ef"/>
    <rect x="0" y="142" width="720" height="136" fill="#d9dedb"/>
    <rect x="292" y="0" width="136" height="420" fill="#d9dedb"/>
    <path d="M0 210H720M360 0V420" stroke="#fff" strokeWidth="4" strokeDasharray="18 18" opacity=".9"/>
    <path d="M275 132v-34M445 288v34M282 295h-34M438 125h34" stroke="#fff" strokeWidth="8"/>
    <g className={step === 1 ? "demoVehicle active" : "demoVehicle"} transform="translate(319 306)"><rect width="82" height="50" rx="15" fill="#257f6d"/><rect x="18" y="7" width="46" height="36" rx="9" fill="#bfe0d7"/><circle cx="17" cy="50" r="7" fill="#191b1a"/><circle cx="65" cy="50" r="7" fill="#191b1a"/></g>
    <g className={step === 2 ? "demoVehicle active" : "demoVehicle"} transform="translate(484 177) rotate(90 41 25)"><rect width="82" height="50" rx="15" fill="#191b1a"/><rect x="18" y="7" width="46" height="36" rx="9" fill="#d7d9d8"/><circle cx="17" cy="50" r="7" fill="#191b1a"/><circle cx="65" cy="50" r="7" fill="#191b1a"/></g>
    <path d="M360 292V230" stroke="#257f6d" strokeWidth="8" strokeLinecap="round" markerEnd="url(#arrow-green)" opacity={step === 1 ? 1 : .34}/>
    <path d="M470 210H390" stroke="#191b1a" strokeWidth="8" strokeLinecap="round" markerEnd="url(#arrow-ink)" opacity={step === 2 ? 1 : .34}/>
    <g transform="translate(34 28)"><rect width="168" height="48" rx="24" fill="#fff" opacity=".94"/><circle cx="25" cy="24" r="8" fill={step === 1 ? "#257f6d" : "#191b1a"}/><text x="43" y="30" fill="#2d3330" fontSize="19" fontWeight="650">{step === 1 ? "先减速观察" : "让右方车先行"}</text></g>
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
      <span>C1 · 科目一 · 媒体知识卡示例</span>
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
