import { http, HttpResponse } from "msw";

import { API_BASE_URL } from "@/lib/api-client";

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
