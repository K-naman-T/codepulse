import { describe, it, expect, vi, beforeEach } from "vitest";
import { Command } from "commander";
import { createCLI } from "../src/cli.js";

describe("CLI", () => {
  let program: Command;

  beforeEach(() => {
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
    const opts = cmd!.options;
    expect(opts.some((o) => o.name() === "path")).toBe(true);
  });

  it("test_index_command", () => {
    const cmd = program.commands.find((c) => c.name() === "index");
    expect(cmd).toBeDefined();
    const opts = cmd!.options;
    expect(opts.some((o) => o.attributeName() === "useScip")).toBe(true);
  });

  it("test_search_command", () => {
    const cmd = program.commands.find((c) => c.name() === "search");
    expect(cmd).toBeDefined();
    const opts = cmd!.options;
    expect(opts.some((o) => o.attributeName() === "kind")).toBe(true);
    expect(opts.some((o) => o.attributeName() === "limit")).toBe(true);
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
});
