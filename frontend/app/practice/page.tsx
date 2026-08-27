import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { StudentShell } from "@/components/layout/student-shell";
import { PracticeWorkspace } from "@/features/practice/practice-workspace";
export default async function Page({searchParams}:{searchParams:Promise<{mode?:string;license?:string;subject?:string}>}){if(!(await cookies()).get("student_session"))redirect("/enter");const {mode,license,subject}=await searchParams;const initialMode=mode==="wrong"||mode==="favorites"?mode:"all";return <StudentShell><PracticeWorkspace initialMode={initialMode} license={license??"C1"} subject={subject??"subject-1"}/></StudentShell>}
