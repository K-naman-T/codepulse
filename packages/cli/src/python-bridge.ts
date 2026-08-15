import { spawn, execFile } from "child_process";

export interface PythonVersion {
  major: number;
  minor: number;
  micro: number;
}

export interface SpawnResult {
  exitCode: number | null;
  stdout: string;
  stderr: string;
  timedOut: boolean;
}

export interface SpawnOptions {
  timeout?: number;
  env?: Record<string, string>;
  stdio?: "pipe" | "inherit";
}

export class PythonBridge {
  private pythonPath: string;
  private fallbackArgs: string[];

  constructor(pythonPath: string = "python3", fallbackArgs: string[] = ["-m", "codepulse"]) {
    this.pythonPath = pythonPath;
    this.fallbackArgs = fallbackArgs;
  }

  async detectPython(): Promise<PythonVersion> {
    return new Promise((resolve, reject) => {
      execFile(this.pythonPath, ["--version"], (error, stdout, stderr) => {
        if (error) {
          reject(new Error(`Failed to detect Python: ${error.message}`));
          return;
        }
        const versionStr = stdout.trim() || stderr.trim();
        const match = versionStr.match(/(\d+)\.(\d+)\.(\d+)/);
        if (!match) {
          reject(new Error(`Could not parse Python version from: ${versionStr}`));
          return;
        }
        const version: PythonVersion = {
          major: parseInt(match[1], 10),
          minor: parseInt(match[2], 10),
          micro: parseInt(match[3], 10),
        };
        if (version.major < 3 || (version.major === 3 && version.minor < 10)) {
          reject(
            new Error(
              `Python >= 3.10 required, found ${version.major}.${version.minor}.${version.micro}`
            )
          );
          return;
        }
        resolve(version);
      });
    });
  }

  async spawn(
    command: string,
    args: string[],
    options: SpawnOptions = {}
  ): Promise<SpawnResult> {
    const result = await this.rawSpawn(command, args, options);
    if (result.exitCode !== null || result.timedOut) return result;
    const fallbackResult = await this.rawSpawn(this.pythonPath, [...this.fallbackArgs, ...args], options);
    if (fallbackResult.exitCode !== null) return fallbackResult;
    return {
      exitCode: null,
      stdout: result.stdout,
      stderr: `Command not found: ${command}. Fallback to ${this.pythonPath} ${this.fallbackArgs.join(" ")} also failed: ${result.stderr}`,
      timedOut: result.timedOut,
    };
  }

  private rawSpawn(
    command: string,
    args: string[],
    options: SpawnOptions
  ): Promise<SpawnResult> {
    return new Promise((resolve) => {
      const child = spawn(command, args, {
        env: { ...process.env, ...options.env },
        stdio: options.stdio === "inherit" ? "inherit" : ["pipe", "pipe", "pipe"],
        timeout: options.timeout ?? 300_000,
        killSignal: "SIGKILL",
      });

      let stdout = "";
      let stderr = "";

      child.stdout?.on("data", (data: Buffer) => {
        stdout += data.toString();
      });

      child.stderr?.on("data", (data: Buffer) => {
        stderr += data.toString();
      });

      child.on("close", (exitCode, signal) => {
        resolve({ exitCode, stdout, stderr, timedOut: signal !== null });
      });

      child.on("error", (err) => {
        stderr += err.message;
        resolve({ exitCode: null, stdout, stderr, timedOut: false });
      });
    });
  }
}
