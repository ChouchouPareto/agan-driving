import { Suspense } from "react";
import { StudentShell } from "@/components/layout/student-shell";
import { MediaLearningDemo } from "@/features/media/media-learning-demo";

export default function MediaDemoPage() {
  return <Suspense fallback={<main className="main"><div className="card status">正在加载示例…</div></main>}><StudentShell><MediaLearningDemo/></StudentShell></Suspense>;
}
