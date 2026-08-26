import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const COOKIE = "student_session";
const upstream = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000/api/v1";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const url = `${upstream}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const token = (await cookies()).get(COOKIE)?.value;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (token) headers.set("authorization", `Bearer ${token}`);
  const requestId = request.headers.get("x-request-id") ?? crypto.randomUUID();
  headers.set("x-request-id", requestId);
  const response = await fetch(url, {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
    cache: "no-store",
  });
  const responseHeaders = new Headers();
  responseHeaders.set("content-type", response.headers.get("content-type") ?? "application/json");
  responseHeaders.set("x-request-id", requestId);
  if (path.join("/") === "auth/invitations/verify" && response.ok) {
    const payload = await response.json();
    const next = NextResponse.json({ student_id: payload.student_id, anonymous_id: payload.anonymous_id }, { status: response.status, headers: responseHeaders });
    if (payload.access_token) {
      next.cookies.set(COOKIE, payload.access_token, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 60 * 60 * 8 });
    }
    return next;
  }
  return new NextResponse(response.body, { status: response.status, headers: responseHeaders });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
