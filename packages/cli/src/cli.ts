import { Command } from "commander";
import { PythonBridge } from "./python-bridge.js";
import { Installer } from "./installer.js";

const VERSION = "0.1.0";

async function callPython(
  bridge: PythonBridge,
  args: string[],
  options: Parameters<PythonBridge["spawn"]>[2] = {}
): Promise<void> {
  const result = Object.keys(options).length > 0
    ? await bridge.spawn("codepulse", args, options)
    : await bridge.spawn("codepulse", args);
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.exitCode !== 0) {
    process.exit(result.exitCode ?? 1);
  }
}

function delegateCommand(
  program: Command,
  name: string,
  description: string,
  pythonCommand: string = name
): void {
  program
    .command(name)
    .description(description)
    .allowUnknownOption(true)
    .helpOption("-h, --ts-help", "display TypeScript wrapper help")
    .argument("[args...]", "Arguments passed to Python CodePulse")
    .action(async (args: string[] = []) => {
      const bridge = new PythonBridge();
      const spawnOptions = pythonCommand === "mcp" ? { stdio: "inherit" as const } : {};
      await callPython(bridge, [pythonCommand, ...args], spawnOptions);
    });
}

export function createCLI(): Command {
  const program = new Command();

  program
    .name("codepulse")
    .version(VERSION)
    .description("Code intelligence graph — parse, query, and explore codebases");

  delegateCommand(program, "init", "Initialize a project for code graph indexing");
  delegateCommand(program, "index", "Index all code files to build the graph");
  delegateCommand(program, "search", "Search indexed symbols");
  delegateCommand(program, "callers", "Show nodes that call a given symbol");
  delegateCommand(program, "callees", "Show symbols called by a given node");
  delegateCommand(program, "trace", "Show call path between two symbols");
  delegateCommand(program, "impact", "Show impact radius of a symbol");
  delegateCommand(program, "serve", "Start MCP server over stdio for AI agent integration", "mcp");

  program
    .command("install")
    .description("Auto-detect OpenCode and install CodePulse MCP config")
    .action(async () => {
      const installer = new Installer();
      installer.install();
      console.log("CodePulse installed for OpenCode.");
      console.log("MCP config written to ~/.config/opencode/opencode.json");
      console.log("AGENTS.md written to current directory.");
    });

  program
    .command("uninstall")
    .description("Remove CodePulse from OpenCode config")
    .action(async () => {
      const installer = new Installer();
      installer.uninstall();
      console.log("CodePulse removed from OpenCode config.");
    });

  return program;
}
