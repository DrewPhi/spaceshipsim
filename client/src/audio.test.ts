import { describe, expect, it } from "vitest";
import { alertKey, buildAudibleMonitor, classifyMonitorProfile, highestAlertSeverity } from "./audio";

describe("console audio", () => {
  it("prioritizes master warning severity", () => {
    expect(highestAlertSeverity([{ severity: "status" }, { severity: "critical" }, { severity: "caution" }])).toBe("critical");
    expect(highestAlertSeverity([])).toBeNull();
  });

  it("builds a bounded realistic receiver monitor", () => {
    const output = buildAudibleMonitor([0, 1, 0, -1], 64, 8_000, 1);
    expect(output).toHaveLength(8_000);
    expect(Math.max(...output)).toBeLessThanOrEqual(.320001);
    expect(Math.min(...output)).toBeGreaterThanOrEqual(-.320001);
    expect(output[0]).toBe(0);
    expect(output.at(-1)).toBeCloseTo(0);
  });

  it("renders distinct deterministic acoustic profiles from the same scientific trace", () => {
    const samples = Array.from({ length: 64 }, (_, index) => Math.sin(index * .47) * (.55 + .35 * Math.sin(index * .13)));
    const language = buildAudibleMonitor(samples, 64, 8_000, .5, 18, "language");
    const telemetry = buildAudibleMonitor(samples, 64, 8_000, .5, 18, "telemetry");
    const noise = buildAudibleMonitor(samples, 64, 8_000, .5, 18, "noise");
    expect(language).toHaveLength(4_000);
    expect(telemetry).toHaveLength(4_000);
    expect(noise).toHaveLength(4_000);
    expect(Array.from(language.slice(200, 260))).not.toEqual(Array.from(telemetry.slice(200, 260)));
    expect(Array.from(telemetry.slice(200, 260))).not.toEqual(Array.from(noise.slice(200, 260)));
    expect(Array.from(buildAudibleMonitor(samples, 64, 8_000, .5, 18, "language"))).toEqual(Array.from(language));
  });

  it("classifies receiver traces into a presentation profile without mutating the samples", () => {
    const samples = Array.from({ length: 96 }, (_, index) => Math.sin(index * .31) + .22 * Math.sin(index * .07));
    const before = [...samples];
    expect(["language", "telemetry", "noise"]).toContain(classifyMonitorProfile(samples));
    expect(samples).toEqual(before);
  });

  it("uses severity, source, and message as an alert identity", () => {
    expect(alertKey({ severity: "caution", source: "THERMAL", message: "Heat high" })).toBe("caution:THERMAL:Heat high");
  });
});
