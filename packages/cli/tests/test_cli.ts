import { describe, it, expect, vi, beforeEach } from "vitest";
import { Command } from "commander";
import { createCLI } from "../src/cli.js";

vi.mock("../src/python-bridge.js", () => {
  const mockSpawn = vi.fn();
  function PythonBridge() {
    this.spawn = mockSpawn;
    this.detectPython = vi.fn();
  }
  return { PythonBridge, mockSpawn };
});

import { mockSpawn } from "../src/python-bridge.js";

describe("CLI", () => {
  let program: Command;

  beforeEach(() => {
    vi.clearAllMocks();
    mockSpawn.mockResolvedValue({ exitCode: 0, stdout: "", stderr: "", timedOut: false });
    program = createCLI();
  });

  it("test_help_output", async () => {
    const help = program.helpInformation();
    expect(help).toContain("codepulse");
    expect(help).toContain("init");
    expect(help).toContain("index");
    expect(help).toContain("search");
    expect(help).toContain("callers");
    expect(help).toContain("callees");
    expect(help).toContain("trace");
    expect(help).toContain("serve");
    expect(help).toContain("install");
    expect(help).toContain("uninstall");
  });

  it("test_init_command", () => {
    const cmd = program.commands.find((c) => c.name() === "init");
    expect(cmd).toBeDefined();
    expect(cmd!.description()).toBeTruthy();
  });

  it("test_index_command", () => {
    const cmd = program.commands.find((c) => c.name() === "index");
    expect(cmd).toBeDefined();
    expect(cmd!.description()).toBeTruthy();
  });

  it("test_search_command", () => {
    const cmd = program.commands.find((c) => c.name() === "search");
    expect(cmd).toBeDefined();
    expect(cmd!.description()).toBeTruthy();
  });

  it("test_callers_command", () => {
    const cmd = program.commands.find((c) => c.name() === "callers");
    expect(cmd).toBeDefined();
  });

  it("test_version_flag", () => {
    expect(program.version()).toBe("0.1.0");
  });

  it("test_all_commands_registered", () => {
    const names = program.commands.map((c) => c.name());
    expect(names).toContain("init");
    expect(names).toContain("index");
    expect(names).toContain("search");
    expect(names).toContain("callers");
    expect(names).toContain("callees");
    expect(names).toContain("trace");
    expect(names).toContain("serve");
    expect(names).toContain("install");
    expect(names).toContain("uninstall");
  });

  it("test_init_delegates_to_python", async () => {
    await program.parseAsync(["init", "--path", "."], { from: "user" });
    expect(mockSpawn).toHaveBeenCalledWith("codepulse", ["init", "--path", "."]);
  });

  it("test_index_help_delegates_to_python", async () => {
    await program.parseAsync(["index", "--help"], { from: "user" });
    expect(mockSpawn).toHaveBeenCalledWith("codepulse", ["index", "--help"]);
  });

  it("test_search_delegates_to_python", async () => {
    await program.parseAsync(
      ["search", "main", "--kind", "function", "--limit", "20"],
      { from: "user" }
    );
    expect(mockSpawn).toHaveBeenCalledWith("codepulse", ["search", "main", "--kind", "function", "--limit", "20"]);
  });

  it("test_callers_delegates_to_python", async () => {
    await program.parseAsync(
      ["callers", "test::helper", "--depth", "1"],
      { from: "user" }
    );
    expect(mockSpawn).toHaveBeenCalledWith("codepulse", ["callers", "test::helper", "--depth", "1"]);
  });

  it("test_callees_delegates_to_python", async () => {
    await program.parseAsync(
      ["callees", "test::main", "--depth", "1"],
      { from: "user" }
    );
    expect(mockSpawn).toHaveBeenCalledWith("codepulse", ["callees", "test::main", "--depth", "1"]);
  });

  it("test_trace_delegates_to_python", async () => {
    await program.parseAsync(
      ["trace", "test::main", "test::helper", "--depth", "3"],
      { from: "user" }
    );
    expect(mockSpawn).toHaveBeenCalledWith("codepulse", ["trace", "test::main", "test::helper", "--depth", "3"]);
  });

  it("test_impact_delegates_to_python", async () => {
    await program.parseAsync(
      ["impact", "test::main", "--depth", "3"],
      { from: "user" }
    );
    expect(mockSpawn).toHaveBeenCalledWith("codepulse", ["impact", "test::main", "--depth", "3"]);
  });

  it("test_serve_delegates_to_python_mcp", async () => {
    await program.parseAsync(["serve"], { from: "user" });
    expect(mockSpawn).toHaveBeenCalledWith("codepulse", ["mcp"], { stdio: "inherit" });
  });

  it("test_serve_help_delegates_to_python_mcp_help", async () => {
    await program.parseAsync(["serve", "--help"], { from: "user" });
    expect(mockSpawn).toHaveBeenCalledWith("codepulse", ["mcp", "--help"], { stdio: "inherit" });
  });

  it("test_delegation_exits_nonzero_when_bridge_cannot_spawn", async () => {
    mockSpawn.mockResolvedValue({
      exitCode: null,
      stdout: "",
      stderr: "command not found",
      timedOut: false,
    });
    const stderrSpy = vi.spyOn(process.stderr, "write").mockImplementation(() => true);
    const exitSpy = vi.spyOn(process, "exit").mockImplementation(((code?: number) => {
      throw new Error(`exit ${code}`);
    }) as never);

    await expect(program.parseAsync(["search", "main"], { from: "user" })).rejects.toThrow("exit 1");
    expect(exitSpy).toHaveBeenCalledWith(1);

    stderrSpy.mockRestore();
    exitSpy.mockRestore();
  });
});
