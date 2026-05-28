import { PythonBridge } from "./python-bridge.js";

export interface MCPServerOptions {
  pythonPath?: string;
}

export class CodePulseMCPServer {
  private bridge: PythonBridge;

  constructor(options: MCPServerOptions = {}) {
    this.bridge = new PythonBridge(options.pythonPath ?? "python3");
  }

  async start(): Promise<void> {
    const result = await this.bridge.spawn("codepulse", ["mcp"], { stdio: "inherit" });
    if (result.exitCode !== 0) {
      throw new Error(result.stderr || "CodePulse MCP server failed");
    }
    if (result.stdout) process.stdout.write(result.stdout);
    if (result.stderr) process.stderr.write(result.stderr);
  }
}
