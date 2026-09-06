import { describe, expect, it } from "vitest";
import { assignmentForCrew, formatTime, gaugeLevel, gaugePoint, normalizeGauge, percent, title } from "./logic";

describe("crew layout", () => {
  it("uses an integrated solo station", () => {
    expect(assignmentForCrew(1)).toEqual(["Integrated Command"]);
  });

  it("progressively separates responsibilities", () => {
    expect(assignmentForCrew(4)).toHaveLength(4);
    expect(assignmentForCrew(6)).toEqual(["Command", "Flight", "Engineering", "Science", "Communications", "Tactical"]);
  });

  it("keeps core stations for larger crews", () => {
    expect(assignmentForCrew(20)).toHaveLength(6);
  });
});

describe("analogue instruments", () => {
  it("normalizes and clamps needle values", () => {
    expect(normalizeGauge(75, 0, 100)).toBe(.75);
    expect(normalizeGauge(150, 0, 100)).toBe(1);
    expect(normalizeGauge(-10, 0, 100)).toBe(0);
  });

  it("classifies high and low hazards", () => {
    expect(gaugeLevel(.8, .75, 1, "high")).toBe("caution");
    expect(gaugeLevel(1.1, .75, 1, "high")).toBe("critical");
    expect(gaugeLevel(.5, .7, .4, "low")).toBe("caution");
    expect(gaugeLevel(.2, .7, .4, "low")).toBe("critical");
  });

  it("places the needle along an upper semicircle", () => {
    expect(gaugePoint(0, 70)[0]).toBeCloseTo(30);
    expect(gaugePoint(.5, 70)[1]).toBeCloseTo(30);
    expect(gaugePoint(1, 70)[0]).toBeCloseTo(170);
  });
});

describe("instrument formatting", () => {
  it("formats universe time without wall-clock assumptions", () => {
    expect(formatTime(3_661_000)).toBe("01:01:01");
  });

  it("formats labels and normalized values", () => {
    expect(title("artificial_signal")).toBe("Artificial Signal");
    expect(percent(.734)).toBe("73%");
  });
});
