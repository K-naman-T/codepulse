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
}

export class PythonBridge {
  private pythonPath: string;

  constructor(pythonPath: string = "python3") {
    this.pythonPath = pythonPath;
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
    name: string,
    args: string[],
    options: SpawnOptions = {}
  ): Promise<SpawnResult> {
    return new Promise((resolve) => {
      const timeout = options.timeout ?? 300_000;
      const child = spawn(this.pythonPath, args, {
        env: { ...process.env, ...options.env },
        stdio: ["pipe", "pipe", "pipe"],
      });

      let stdout = "";
      let stderr = "";
      let timedOut = false;

      const timer = setTimeout(() => {
        timedOut = true;
        child.kill("SIGTERM");
        setTimeout(() => {
          try { child.kill("SIGKILL"); } catch { /* ignore */ }
        }, 5000);
      }, timeout);

      child.stdout?.on("data", (data: Buffer) => {
        stdout += data.toString();
      });

      child.stderr?.on("data", (data: Buffer) => {
        stderr += data.toString();
      });

      child.on("close", (exitCode) => {
        clearTimeout(timer);
        resolve({ exitCode, stdout, stderr, timedOut });
      });

      child.on("error", (err) => {
        clearTimeout(timer);
        stderr += err.message;
        resolve({ exitCode: null, stdout, stderr, timedOut });
      });
    });
  }
}
