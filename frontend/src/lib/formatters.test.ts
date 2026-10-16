import { describe, expect, it } from "vitest";
import { formatQuantity } from "./formatters";

describe("formatQuantity", () => {
  it("strips trailing zeros from API decimal strings", () => {
    expect(formatQuantity("1.000")).toBe("1");
    expect(formatQuantity("10.500")).toBe("10.5");
    expect(formatQuantity("0.125")).toBe("0.125");
  });

  it("adds thousand separators", () => {
    expect(formatQuantity("200000.000")).toBe("200,000");
    expect(formatQuantity(1234.5)).toBe("1,234.5");
  });

  it("shows a dash for empty values", () => {
    expect(formatQuantity(null)).toBe("—");
    expect(formatQuantity(undefined)).toBe("—");
    expect(formatQuantity("")).toBe("—");
  });
});
