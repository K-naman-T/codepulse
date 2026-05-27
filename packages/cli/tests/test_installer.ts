import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, writeFileSync, mkdirSync, rmSync, readFileSync, existsSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import { Installer } from "../src/installer.js";

describe("Installer", () => {
  let tmpDir: string;
  let configDir: string;
  let projectDir: string;
  let installer: Installer;

  beforeEach(() => {
    tmpDir = mkdtempSync(join(tmpdir(), "codepulse-test-"));
    configDir = join(tmpDir, ".config", "opencode");
    projectDir = join(tmpDir, "project");
    mkdirSync(configDir, { recursive: true });
    mkdirSync(projectDir, { recursive: true });
    installer = new Installer({ configDir, projectDir, pythonPath: "python3" });
  });

  afterEach(() => {
    rmSync(tmpDir, { recursive: true, force: true });
  });

  it("test_detect_none", () => {
    const result = installer.detectOpenCode();
    expect(result).toBeNull();
  });

  it("test_detect_opencode", () => {
    writeFileSync(
      join(configDir, "opencode.json"),
      JSON.stringify({ mcpServers: {} }, null, 2)
    );
    const result = installer.detectOpenCode();
    expect(result).not.toBeNull();
    expect(result!.configPath).toBe(join(configDir, "opencode.json"));
  });

  it("test_install_writes_config", () => {
    writeFileSync(
      join(configDir, "opencode.json"),
      JSON.stringify({ mcpServers: {} }, null, 2)
    );
    installer.install();
    const config = JSON.parse(
      readFileSync(join(configDir, "opencode.json"), "utf-8")
    );
    expect(config.mcpServers["codepulse"]).toBeDefined();
    expect(config.mcpServers["codepulse"].command).toBe("python3");
    expect(config.mcpServers["codepulse"].args).toContain("codepulse");
    expect(config.mcpServers["codepulse"].args).toContain("serve");
  });

  it("test_uninstall_removes_entry", () => {
    writeFileSync(
      join(configDir, "opencode.json"),
      JSON.stringify(
        {
          mcpServers: {
            codepulse: { command: "python3", args: ["-m", "codepulse", "serve"] },
            other: { command: "echo", args: ["hi"] },
          },
        },
        null,
        2
      )
    );
    installer.uninstall();
    const config = JSON.parse(
      readFileSync(join(configDir, "opencode.json"), "utf-8")
    );
    expect(config.mcpServers["codepulse"]).toBeUndefined();
    expect(config.mcpServers["other"]).toBeDefined();
  });

  it("test_writes_agents_md", () => {
    writeFileSync(
      join(configDir, "opencode.json"),
      JSON.stringify({ mcpServers: {} }, null, 2)
    );
    installer.install();
    const agentsPath = join(projectDir, "AGENTS.md");
    expect(existsSync(agentsPath)).toBe(true);
    const content = readFileSync(agentsPath, "utf-8");
    expect(content).toContain("codepulse");
    expect(content).toContain("MCP");
  });
});
