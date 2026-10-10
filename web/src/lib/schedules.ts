import { apiFetch } from "@/lib/api-client";
import type {
  Schedule,
  ScheduleCreateInput,
  ScheduleList,
  ScheduleUpdateInput,
} from "@/lib/types";

export function listSchedules(input?: {
  start?: string;
  end?: string;
}): Promise<ScheduleList> {
  const params = new URLSearchParams();
  if (input?.start) params.set("start", input.start);
  if (input?.end) params.set("end", input.end);
  const query = params.size > 0 ? `?${params.toString()}` : "";
  return apiFetch<ScheduleList>(`/schedules${query}`);
}

export function listProjectSchedules(projectId: string): Promise<ScheduleList> {
  return apiFetch<ScheduleList>(`/projects/${projectId}/schedules`);
}

export function createSchedule(
  projectId: string,
  input: ScheduleCreateInput,
): Promise<Schedule> {
  return apiFetch<Schedule>(`/projects/${projectId}/schedules`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateSchedule(
  projectId: string,
  scheduleId: string,
  input: ScheduleUpdateInput,
): Promise<Schedule> {
  return apiFetch<Schedule>(`/projects/${projectId}/schedules/${scheduleId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteSchedule(
  projectId: string,
  scheduleId: string,
): Promise<void> {
  return apiFetch<void>(`/projects/${projectId}/schedules/${scheduleId}`, {
    method: "DELETE",
  });
}
