import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { homedir } from "os";
import { PythonBridge } from "./python-bridge.js";

export interface InstallerOptions {
  configDir?: string;
  projectDir?: string;
  pythonPath?: string;
}

export interface OpenCodeConfig {
  configPath: string;
  config: Record<string, unknown>;
}

const AGENTS_MD_CONTENT = `## CodePulse MCP Integration

This project uses CodePulse for code intelligence. The MCP server is configured
automatically via OpenCode.

### Available Tools

- \`search\` — Search indexed symbols by name
- \`context\` — Build ranked context from a task description
- \`trace\` — Find call paths between two symbols
- \`callers\` — Find what calls a symbol
- \`callees\` — Find what a symbol calls
- \`impact\` — Show impact radius of a symbol
- \`node\` — Get source code and signature for a symbol
- \`explore\` — Search symbols grouped by file
- \`status\` — Check index health

### Usage

\`\`\`
codepulse init     # Initialize a project
codepulse index .  # Index the codebase
codepulse serve    # Start MCP server
\`\`\`
`;

export class Installer {
  private configDir: string;
  private projectDir: string;
  private pythonPath: string;

  constructor(options: InstallerOptions = {}) {
    this.configDir = options.configDir ?? join(homedir(), ".config", "opencode");
    this.projectDir = options.projectDir ?? process.cwd();
    this.pythonPath = options.pythonPath ?? "python3";
  }

  detectOpenCode(): OpenCodeConfig | null {
    const configPath = join(this.configDir, "opencode.json");
    if (!existsSync(configPath)) return null;
    try {
      const content = readFileSync(configPath, "utf-8");
      const config = JSON.parse(content);
      return { configPath, config };
    } catch {
      return null;
    }
  }

  install(): void {
    const configPath = join(this.configDir, "opencode.json");
    let config: Record<string, unknown>;

    if (existsSync(configPath)) {
      config = JSON.parse(readFileSync(configPath, "utf-8"));
    } else {
      mkdirSync(this.configDir, { recursive: true });
      config = {};
    }

    const mcpServers = ((config as Record<string, any>).mcpServers as Record<string, any>) ?? {};

    mcpServers["codepulse"] = {
      command: this.pythonPath,
      args: ["-m", "codepulse", "serve"],
      env: {},
    };

    config = { ...config, mcpServers };
    writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n");

    const agentsPath = join(this.projectDir, "AGENTS.md");
    if (!existsSync(agentsPath)) {
      writeFileSync(agentsPath, AGENTS_MD_CONTENT + "\n");
    }
  }

  uninstall(): void {
    const configPath = join(this.configDir, "opencode.json");
    if (!existsSync(configPath)) return;

    const config = JSON.parse(readFileSync(configPath, "utf-8"));
    const mcpServers = (config.mcpServers as Record<string, any>) ?? {};

    delete mcpServers["codepulse"];
    config.mcpServers = mcpServers;

    writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n");
  }
}
