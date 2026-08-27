import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const COOKIE = "staff_session";
const upstream = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000/api/v1";
async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const route = path.join("/");
  const headers = new Headers();
  const contentType = request.headers.get("content-type"); if (contentType) headers.set("content-type", contentType);
  const key = request.headers.get("idempotency-key"); if (key) headers.set("idempotency-key", key);
  const token = (await cookies()).get(COOKIE)?.value; if (token) headers.set("authorization", `Bearer ${token}`);
  const response = await fetch(`${upstream}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, { method: request.method, headers, body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(), cache: "no-store" });
  if (route === "staff/auth/invitations/verify" && response.ok) {
    const payload = await response.json();
    const next = NextResponse.json({ staff_id: payload.staff_id, display_name: payload.display_name, role: payload.role });
    next.cookies.set(COOKIE, payload.access_token, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 60 * 60 * 8 });
    return next;
  }
  return new NextResponse(response.body, { status: response.status, headers: { "content-type": response.headers.get("content-type") ?? "application/json" } });
}
export const GET = proxy; export const POST = proxy; export const PATCH = proxy;
