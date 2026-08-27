import { cookies } from "next/headers"; import { redirect } from "next/navigation";
import { StaffShell } from "@/components/layout/staff-shell"; import { TicketQueue } from "@/features/staff/ticket-queue";
export default async function Page() { if (!(await cookies()).get("staff_session")) redirect("/staff/enter"); return <StaffShell><TicketQueue/></StaffShell>; }
