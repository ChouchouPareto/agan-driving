import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { StudentShell } from "@/components/layout/student-shell";
import { PracticeWorkspace } from "@/features/practice/practice-workspace";
export default async function Page(){if(!(await cookies()).get("student_session"))redirect("/enter");return <StudentShell><PracticeWorkspace/></StudentShell>}
