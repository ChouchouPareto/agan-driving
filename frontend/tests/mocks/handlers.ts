import { http, HttpResponse } from "msw";
export const handlers = [http.get("/api/session", () => HttpResponse.json({ authenticated: false }))];
