import { StaffShell } from "@/components/layout/staff-shell"; import { EvaluationDetail } from "@/features/knowledge/evaluation-detail";
export default async function Page({params}:{params:Promise<{id:string}>}){const {id}=await params;return <StaffShell><EvaluationDetail id={id}/></StaffShell>}
