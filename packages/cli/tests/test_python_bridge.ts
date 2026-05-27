import { describe, it, expect, vi, beforeEach } from "vitest";
import { PythonBridge } from "../src/python-bridge.js";

describe("PythonBridge", () => {
  let bridge: PythonBridge;

  beforeEach(() => {
    bridge = new PythonBridge();
  });

  it("test_detect_python", async () => {
    const version = await bridge.detectPython();
    expect(version).toBeDefined();
    expect(version.major).toBeGreaterThanOrEqual(3);
    expect(version.minor).toBeGreaterThanOrEqual(10);
  });

  it("test_spawn_success", async () => {
    const result = await bridge.spawn("test_python_bridge", ["-c", "print('hello')"]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("hello");
    expect(result.timedOut).toBe(false);
  });

  it("test_spawn_error", async () => {
    const result = await bridge.spawn("test_python_bridge", ["-c", "import sys; sys.exit(1)"]);
    expect(result.exitCode).toBe(1);
    expect(result.timedOut).toBe(false);
  });

  it("test_spawn_timeout", async () => {
    const result = await bridge.spawn(
      "test_python_bridge",
      ["-c", "import time; time.sleep(10)"],
      { timeout: 100 }
    );
    expect(result.timedOut).toBe(true);
    expect(result.exitCode).toBe(null);
  });

  it("test_spawn_with_args", async () => {
    const result = await bridge.spawn("test_python_bridge", [
      "-c",
      "import sys; print('ok: ' + sys.argv[1])",
      "hello",
    ]);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("ok: hello");
  });
});
