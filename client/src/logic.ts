export type Station = "integrated" | "command" | "flight" | "engineering" | "science" | "communications" | "tactical";

export const roles: Station[] = ["integrated", "command", "flight", "engineering", "science", "communications", "tactical"];

export const defaultAssignments: Record<number, string[]> = {
  1: ["Integrated Command"],
  2: ["Command / Flight / Tactical", "Engineering / Science / Communications"],
  3: ["Command / Flight", "Engineering / Tactical", "Science / Communications"],
  4: ["Command", "Flight / Tactical", "Engineering", "Science / Communications"],
  5: ["Command", "Flight / Tactical", "Engineering", "Science", "Communications"],
  6: ["Command", "Flight", "Engineering", "Science", "Communications", "Tactical"],
};

export function assignmentForCrew(count: number): string[] {
  if (count <= 1) return defaultAssignments[1];
  if (count >= 6) return defaultAssignments[6];
  return defaultAssignments[Math.floor(count)];
}

export function title(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatTime(milliseconds: number): string {
  const seconds = Math.floor(milliseconds / 1000);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
}

export type GaugeLevel = "nominal" | "caution" | "critical";

export function normalizeGauge(value: number, minimum: number, maximum: number): number {
  if (maximum <= minimum) return 0;
  return Math.min(1, Math.max(0, (value - minimum) / (maximum - minimum)));
}

export function gaugeLevel(
  value: number,
  warning: number | undefined,
  critical: number | undefined,
  dangerWhen: "high" | "low" = "high",
): GaugeLevel {
  if (warning === undefined || critical === undefined) return "nominal";
  if (dangerWhen === "high") {
    if (value >= critical) return "critical";
    if (value >= warning) return "caution";
  } else {
    if (value <= critical) return "critical";
    if (value <= warning) return "caution";
  }
  return "nominal";
}

export function gaugePoint(fraction: number, radius: number): [number, number] {
  const clamped = Math.min(1, Math.max(0, fraction));
  const angle = Math.PI * (1 - clamped);
  return [100 + Math.cos(angle) * radius, 100 - Math.sin(angle) * radius];
}
