import { beforeEach, describe, expect, it, vi } from "vitest";
import { CodePulseMCPServer } from "../src/mcp.js";

vi.mock("../src/python-bridge.js", () => {
  const mockSpawn = vi.fn();
  function PythonBridge() {
    this.spawn = mockSpawn;
    this.detectPython = vi.fn();
  }
  return { PythonBridge, mockSpawn };
});

import { mockSpawn } from "../src/python-bridge.js";

describe("CodePulseMCPServer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSpawn.mockResolvedValue({ exitCode: 0, stdout: "", stderr: "", timedOut: false });
  });

  it("delegates MCP serving to Python", async () => {
    const server = new CodePulseMCPServer();

    await server.start();

    expect(mockSpawn).toHaveBeenCalledWith("codepulse", ["mcp"], { stdio: "inherit" });
  });

  it("throws when the Python MCP process fails", async () => {
    mockSpawn.mockResolvedValue({
      exitCode: 1,
      stdout: "",
      stderr: "mcp failed",
      timedOut: false,
    });
    const server = new CodePulseMCPServer();

    await expect(server.start()).rejects.toThrow("mcp failed");
  });
});
