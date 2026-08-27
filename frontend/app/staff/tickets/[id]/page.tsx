import { cookies } from "next/headers"; import { redirect } from "next/navigation";
import { StaffShell } from "@/components/layout/staff-shell"; import { StaffTicketDetail } from "@/features/staff/ticket-detail";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { if (!(await cookies()).get("staff_session")) redirect("/staff/enter"); const { id } = await params; return <StaffShell><StaffTicketDetail id={id}/></StaffShell>; }
