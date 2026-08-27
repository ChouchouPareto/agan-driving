import { cookies } from "next/headers"; import { redirect } from "next/navigation";
import { StaffShell } from "@/components/layout/staff-shell"; import { KnowledgeList } from "@/features/knowledge/knowledge-list";
export default async function Page() { if (!(await cookies()).get("staff_session")) redirect("/staff/enter"); return <StaffShell><KnowledgeList/></StaffShell>; }
