import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { StudentShell } from "@/components/layout/student-shell";
import { MockExamWorkspace } from "@/features/practice/mock-exam-workspace";

export default async function Page({ searchParams }: { searchParams: Promise<{ license?: string; subject?: string }> }) {
  if (!(await cookies()).get("student_session")) redirect("/enter");
  const { license, subject } = await searchParams;
  return <StudentShell><MockExamWorkspace license={license ?? "C1"} subject={subject ?? "subject-1"}/></StudentShell>;
}
