import { Command } from "commander";
import { PythonBridge } from "./python-bridge.js";
import { Installer } from "./installer.js";
import { homedir } from "os";
import { join } from "path";
import Database from "better-sqlite3";

const DEFAULT_DB_PATH = join(homedir(), ".codepulse", "graph.db");
const VERSION = "0.1.0";

interface NodeRow {
  id: string;
  file_path: string;
  name: string;
  kind: string;
  signature: string;
  line_start: number;
  line_end: number;
  parent_id: string | null;
  language: string;
  metadata: string;
}

interface EdgeRow {
  source_id: string;
  target_id: string;
  kind: string;
  file_path: string;
  line_number: number;
}

function openDb(dbPath?: string): Database.Database {
  const path = dbPath || DEFAULT_DB_PATH;
  const db = new Database(path);
  db.pragma("journal_mode = WAL");
  return db;
}

function queryNodes(
  db: Database.Database,
  sql: string,
  params: any[] = []
): NodeRow[] {
  return db.prepare(sql).all(...params) as NodeRow[];
}

function queryEdges(
  db: Database.Database,
  sql: string,
  params: any[] = []
): EdgeRow[] {
  return db.prepare(sql).all(...params) as EdgeRow[];
}

async function callPython(bridge: PythonBridge, args: string[]): Promise<void> {
  const result = await bridge.spawn("codepulse", args);
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.exitCode !== 0 && result.exitCode !== null) {
    process.exit(result.exitCode);
  }
}

export function createCLI(): Command {
  const program = new Command();

  program
    .name("codepulse")
    .version(VERSION)
    .description("Code intelligence graph — parse, query, and explore codebases");

  program
    .command("init")
    .description("Initialize a project for code graph indexing")
    .option("--path <path>", "Project path", ".")
    .action(async (opts) => {
      const bridge = new PythonBridge();
      await callPython(bridge, ["init", "--path", opts.path]);
    });

  program
    .command("index")
    .description("Index all code files to build the graph")
    .argument("[path]", "Path to index", ".")
    .option("--use-scip", "Use SCIP indexer for accurate call graph")
    .action(async (path, opts) => {
      const bridge = new PythonBridge();
      const args = ["index", path || "."];
      if (opts.useScip) args.push("--use-scip");
      await callPython(bridge, args);
    });

  program
    .command("search")
    .description("Search indexed symbols")
    .argument("<query>", "Search query")
    .option("--kind <kind>", "Filter by kind: function, class, method")
    .option("--limit <limit>", "Max results", "20")
    .action((query, opts) => {
      const db = openDb();
      const kind = opts.kind || null;
      const limit = parseInt(opts.limit || "20", 10);

      let sql: string;
      let params: any[];

      try {
        if (kind) {
          sql = `
            SELECT n.* FROM nodes n
            INNER JOIN nodes_fts fts ON n.rowid = fts.rowid
            WHERE nodes_fts MATCH ? AND n.kind = ?
            LIMIT ?
          `;
          params = [query, kind, limit];
        } else {
          sql = `
            SELECT n.* FROM nodes n
            INNER JOIN nodes_fts fts ON n.rowid = fts.rowid
            WHERE nodes_fts MATCH ?
            LIMIT ?
          `;
          params = [query, limit];
        }
        const nodes = queryNodes(db, sql, params);
        if (nodes.length === 0) {
          console.log("No results found.");
          return;
        }
        for (const node of nodes) {
          const suffix = node.kind ? ` (${node.kind})` : "";
          console.log(`  ${node.name}${suffix}`);
          console.log(`  ${node.file_path}:${node.line_start}`);
          if (node.signature) console.log(`  ${node.signature.slice(0, 120)}`);
          console.log();
        }
      } catch {
        console.log("No results found.");
      } finally {
        db.close();
      }
    });

  program
    .command("callers")
    .description("Show nodes that call a given symbol")
    .argument("<node-id>", "Node ID")
    .option("--depth <depth>", "Traversal depth", "1")
    .action((nodeId, opts) => {
      const db = openDb();
      const depth = parseInt(opts.depth || "1", 10);

      const edges = queryEdges(
        db,
        `WITH RECURSIVE callers AS (
          SELECT e.source_id, e.target_id, e.kind, 0 AS d
          FROM edges e WHERE e.target_id = ?
          UNION ALL
          SELECT e.source_id, e.target_id, e.kind, c.d + 1
          FROM edges e JOIN callers c ON e.target_id = c.source_id
          WHERE c.d < ?
        )
        SELECT DISTINCT * FROM callers ORDER BY d, source_id`,
        [nodeId, depth]
      );

      if (edges.length === 0) {
        console.log("No callers found.");
        db.close();
        return;
      }

      const nodeIds = [...new Set(edges.map((e) => e.source_id))];
      const nodes =
        nodeIds.length > 0
          ? queryNodes(
              db,
              `SELECT * FROM nodes WHERE id IN (${nodeIds.map(() => "?").join(",")})`,
              nodeIds
            )
          : [];

      const nodeMap = new Map(nodes.map((n) => [n.id, n]));

      for (const e of edges) {
        const n = nodeMap.get(e.source_id);
        console.log(`  ${n ? n.name : e.source_id} (${e.kind})`);
        if (n) console.log(`  ${n.file_path}:${n.line_start}`);
        console.log();
      }
      db.close();
    });

  program
    .command("callees")
    .description("Show symbols called by a given node")
    .argument("<node-id>", "Node ID")
    .option("--depth <depth>", "Traversal depth", "1")
    .action((nodeId, opts) => {
      const db = openDb();
      const depth = parseInt(opts.depth || "1", 10);

      const edges = queryEdges(
        db,
        `WITH RECURSIVE callees AS (
          SELECT e.source_id, e.target_id, e.kind, 0 AS d
          FROM edges e WHERE e.source_id = ?
          UNION ALL
          SELECT e.source_id, e.target_id, e.kind, c.d + 1
          FROM edges e JOIN callees c ON e.source_id = c.target_id
          WHERE c.d < ?
        )
        SELECT DISTINCT * FROM callees ORDER BY d, target_id`,
        [nodeId, depth]
      );

      if (edges.length === 0) {
        console.log("No callees found.");
        db.close();
        return;
      }

      const nodeIds = [...new Set(edges.map((e) => e.target_id))];
      const nodes =
        nodeIds.length > 0
          ? queryNodes(
              db,
              `SELECT * FROM nodes WHERE id IN (${nodeIds.map(() => "?").join(",")})`,
              nodeIds
            )
          : [];

      const nodeMap = new Map(nodes.map((n) => [n.id, n]));

      for (const e of edges) {
        const n = nodeMap.get(e.target_id);
        console.log(`  ${n ? n.name : e.target_id} (${e.kind})`);
        if (n) console.log(`  ${n.file_path}:${n.line_start}`);
        console.log();
      }
      db.close();
    });

  program
    .command("trace")
    .description("Show impact radius of a symbol")
    .argument("<node-id>", "Node ID")
    .option("--depth <depth>", "Impact depth", "3")
    .action((nodeId, opts) => {
      const db = openDb();
      const depth = parseInt(opts.depth || "3", 10);

      const edges = queryEdges(
        db,
        `WITH RECURSIVE impact AS (
          SELECT e.source_id, e.target_id, e.kind, 0 AS d
          FROM edges e WHERE e.source_id = ? OR e.target_id = ?
          UNION ALL
          SELECT e.source_id, e.target_id, e.kind, i.d + 1
          FROM edges e JOIN impact i ON (e.source_id = i.target_id OR e.target_id = i.source_id)
          WHERE i.d < ?
        )
        SELECT DISTINCT * FROM impact ORDER BY d, source_id, target_id`,
        [nodeId, nodeId, depth]
      );

      if (edges.length === 0) {
        console.log("No impact found.");
        db.close();
        return;
      }

      const nodeIds = [
        ...new Set(edges.flatMap((e) => [e.source_id, e.target_id])),
      ];
      const nodes =
        nodeIds.length > 0
          ? queryNodes(
              db,
              `SELECT * FROM nodes WHERE id IN (${nodeIds.map(() => "?").join(",")})`,
              nodeIds
            )
          : [];

      const nodeMap = new Map(nodes.map((n) => [n.id, n]));
      const byDepth = new Map<number, { name: string; kind: string; file: string; line: number }[]>();

      for (const e of edges) {
        const d = (e as any).d as number;
        if (!byDepth.has(d)) byDepth.set(d, []);
        for (const nid of [e.source_id, e.target_id]) {
          const n = nodeMap.get(nid);
          if (n && !byDepth.get(d)!.some((x) => x.name === n.name)) {
            byDepth.get(d)!.push({
              name: n.name,
              kind: n.kind,
              file: n.file_path,
              line: n.line_start,
            });
          }
        }
      }

      for (const [level, nodes] of [...byDepth.entries()].sort(([a], [b]) => a - b)) {
        console.log(`Depth ${level}:`);
        for (const n of nodes) {
          console.log(`  ${n.name} (${n.kind})`);
          console.log(`  ${n.file}:${n.line}`);
          console.log();
        }
      }
      db.close();
    });

  program
    .command("serve")
    .description("Start MCP server over stdio for AI agent integration")
    .action(async () => {
      const { CodePulseMCPServer } = await import("./mcp.js");
      const { Server } = await import(
        "@modelcontextprotocol/sdk/server/index.js"
      );
      const { StdioServerTransport } = await import(
        "@modelcontextprotocol/sdk/server/stdio.js"
      );
      const {
        ListToolsRequestSchema,
        CallToolRequestSchema,
      } = await import("@modelcontextprotocol/sdk/types.js");

      const mcpServer = new CodePulseMCPServer({ dbPath: DEFAULT_DB_PATH });

      const server = new Server(
        { name: "codepulse", version: VERSION },
        { capabilities: { tools: {} } }
      );

      const TOOLS = [
        {
          name: "search",
          description: "Search indexed symbols by name using FTS5",
          inputSchema: {
            type: "object",
            properties: {
              query: { type: "string", description: "Search query" },
              kind: {
                type: "string",
                description: "Filter by kind (function, class, method)",
              },
              limit: { type: "number", description: "Max results", default: 20 },
            },
            required: ["query"],
          },
        },
        {
          name: "context",
          description: "Build ranked code context from a task description",
          inputSchema: {
            type: "object",
            properties: {
              task: { type: "string", description: "Task description" },
              maxNodes: {
                type: "number",
                description: "Max context nodes",
                default: 30,
              },
            },
            required: ["task"],
          },
        },
        {
          name: "trace",
          description: "Find a call path between two symbols",
          inputSchema: {
            type: "object",
            properties: {
              source: { type: "string", description: "Source node ID" },
              target: { type: "string", description: "Target node ID" },
            },
            required: ["source", "target"],
          },
        },
        {
          name: "callers",
          description: "Find what calls a symbol",
          inputSchema: {
            type: "object",
            properties: {
              nodeId: { type: "string", description: "Node ID" },
              depth: { type: "number", description: "Traversal depth", default: 1 },
            },
            required: ["nodeId"],
          },
        },
        {
          name: "callees",
          description: "Find what a symbol calls",
          inputSchema: {
            type: "object",
            properties: {
              nodeId: { type: "string", description: "Node ID" },
              depth: { type: "number", description: "Traversal depth", default: 1 },
            },
            required: ["nodeId"],
          },
        },
        {
          name: "impact",
          description: "Show impact radius of a symbol (both callers and callees)",
          inputSchema: {
            type: "object",
            properties: {
              nodeId: { type: "string", description: "Node ID" },
              depth: { type: "number", description: "Impact depth", default: 3 },
            },
            required: ["nodeId"],
          },
        },
        {
          name: "node",
          description: "Get source/signature details for a single symbol",
          inputSchema: {
            type: "object",
            properties: {
              nodeId: { type: "string", description: "Node ID" },
            },
            required: ["nodeId"],
          },
        },
        {
          name: "explore",
          description: "Search multiple symbols grouped by file",
          inputSchema: {
            type: "object",
            properties: {
              query: { type: "string", description: "Search query" },
            },
            required: ["query"],
          },
        },
        {
          name: "status",
          description: "Check index health (node/edge counts, FTS status)",
          inputSchema: {
            type: "object",
            properties: {},
          },
        },
      ];

      server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

      server.setRequestHandler(
        CallToolRequestSchema,
        async (request: any) => {
          const { name, arguments: args } = request.params;
          try {
            const result = mcpServer.handleTool(name, args || {});
            return {
              content: [{ type: "text", text: result }],
            };
          } catch (e) {
            return {
              content: [{ type: "text", text: `Error: ${e}` }],
              isError: true,
            };
          }
        }
      );

      const transport = new StdioServerTransport();
      await server.connect(transport);
    });

  program
    .command("install")
    .description("Auto-detect OpenCode and install CodePulse MCP config")
    .action(async () => {
      const installer = new Installer();
      const detected = installer.detectOpenCode();
      if (!detected) {
        console.log("No OpenCode config found at ~/.config/opencode/opencode.json");
        console.log("Creating new config and installing CodePulse...");
      }
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
