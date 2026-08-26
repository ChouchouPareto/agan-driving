import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({ authenticated: Boolean((await cookies()).get("student_session")) });
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set("student_session", "", { httpOnly: true, sameSite: "lax", path: "/", maxAge: 0 });
  return response;
}
