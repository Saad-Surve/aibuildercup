import { http, HttpResponse } from "msw";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080/api";

export const handlers = [
  http.get(`${API_BASE_URL}/healthz`, () =>
    HttpResponse.json({ status: "ok" }),
  ),
  http.get(`${API_BASE_URL}/me`, () =>
    HttpResponse.json({
      uid: "demo-user",
      displayName: "Demo Creator",
      email: "demo@example.com",
      onboardingCompleted: true,
      personaVersion: 1,
      preferences: { timezone: "Asia/Kolkata", defaultLanguage: "en" },
    }),
  ),
];
