import { Suspense } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { StudentShell } from "@/components/layout/student-shell";
import { AskWorkspace } from "@/features/questions/ask-workspace";
export default async function AskPage() { if (!(await cookies()).get("student_session")) redirect("/enter"); return <StudentShell><Suspense fallback={<div className="card status">正在加载…</div>}><AskWorkspace/></Suspense></StudentShell>; }
