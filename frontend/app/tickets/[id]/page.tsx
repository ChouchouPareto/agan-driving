import { cookies } from "next/headers"; import { redirect } from "next/navigation";
import { StudentShell } from "@/components/layout/student-shell"; import { StudentTicketDetail } from "@/features/questions/student-ticket-detail";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { if (!(await cookies()).get("student_session")) redirect("/enter"); const { id } = await params; return <StudentShell><StudentTicketDetail id={id}/></StudentShell>; }
