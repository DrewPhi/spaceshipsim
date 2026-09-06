import { describe, expect, it } from "vitest";
import { alertKey, buildAudibleMonitor, highestAlertSeverity } from "./audio";

describe("console audio", () => {
  it("prioritizes master warning severity", () => {
    expect(highestAlertSeverity([{ severity: "status" }, { severity: "critical" }, { severity: "caution" }])).toBe("critical");
    expect(highestAlertSeverity([])).toBeNull();
  });

  it("builds a bounded frequency-shifted receiver monitor", () => {
    const output = buildAudibleMonitor([0, 1, 0, -1], 64, 8_000, 1);
    expect(output).toHaveLength(8_000);
    expect(Math.max(...output)).toBeLessThanOrEqual(.32);
    expect(Math.min(...output)).toBeGreaterThanOrEqual(-.32);
    expect(output[0]).toBe(0);
    expect(output.at(-1)).toBeCloseTo(0);
  });

  it("uses severity, source, and message as an alert identity", () => {
    expect(alertKey({ severity: "caution", source: "THERMAL", message: "Heat high" })).toBe("caution:THERMAL:Heat high");
  });
});
