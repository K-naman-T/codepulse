import Database from "better-sqlite3";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ToolSchema,
} from "@modelcontextprotocol/sdk/types.js";

export interface MCPServerOptions {
  dbPath: string;
  pythonPath?: string;
}

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

export class CodePulseMCPServer {
  private db: Database.Database;
  private dbPath: string;
  private pythonPath: string;

  constructor(options: MCPServerOptions) {
    this.dbPath = options.dbPath;
    this.pythonPath = options.pythonPath ?? "python3";
    this.db = new Database(this.dbPath);
    this.db.pragma("journal_mode = WAL");
  }

  private queryNodes(sql: string, params: any[] = []): NodeRow[] {
    return this.db.prepare(sql).all(...params) as NodeRow[];
  }

  private queryEdges(sql: string, params: any[] = []): EdgeRow[] {
    return this.db.prepare(sql).all(...params) as EdgeRow[];
  }

  handleTool(toolName: string, args: Record<string, unknown>): string {
    switch (toolName) {
      case "search":
        return this.search(args);
      case "context":
        return this.context(args);
      case "trace":
        return this.trace(args);
      case "callers":
        return this.callers(args);
      case "callees":
        return this.callees(args);
      case "impact":
        return this.impact(args);
      case "node":
        return this.node(args);
      case "explore":
        return this.explore(args);
      case "status":
        return this.status();
      default:
        throw new Error(`Unknown tool: ${toolName}`);
    }
  }

  private search(args: Record<string, unknown>): string {
    const query = String(args.query || "");
    const kind = args.kind ? String(args.kind) : null;
    const limit = Number(args.limit) || 20;

    let sql: string;
    let params: any[];

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

    try {
      const nodes = this.queryNodes(sql, params);
      if (nodes.length === 0) return "No symbols found.";
      return nodes
        .map(
          (n) =>
            `${n.name} (${n.kind})\n  File: ${n.file_path}:${n.line_start}${
              n.signature ? `\n  ${n.signature}` : ""
            }`
        )
        .join("\n\n");
    } catch {
      return "No symbols found.";
    }
  }

  private context(args: Record<string, unknown>): string {
    const task = String(args.task || "");
    const maxNodes = Number(args.maxNodes) || 30;

    const words = task
      .toLowerCase()
      .split(/\s+/)
      .filter((w) => w.length > 2);
    if (words.length === 0) return "No context available.";

    const clauses = words.map(() => "name LIKE ?").join(" OR ");
    const params = words.map((w) => `%${w}%`);

    const sql = `SELECT * FROM nodes WHERE ${clauses} LIMIT ?`;
    params.push(String(maxNodes));

    const nodes = this.queryNodes(sql, params);
    if (nodes.length === 0) return "No context available.";

    return nodes
      .map(
        (n) =>
          `${n.name} (${n.kind})\n  File: ${n.file_path}:${n.line_start}${
            n.signature ? `\n  ${n.signature}` : ""
          }`
      )
      .join("\n\n");
  }

  private trace(args: Record<string, unknown>): string {
    const source = String(args.source || "");
    const target = String(args.target || "");

    const edges = this.queryEdges(
      `WITH RECURSIVE path AS (
        SELECT e.source_id, e.target_id, e.kind, e.file_path, e.line_number, 0 AS depth,
               CAST(e.source_id AS TEXT) AS path_str
        FROM edges e WHERE e.source_id = ?
        UNION ALL
        SELECT e.source_id, e.target_id, e.kind, e.file_path, e.line_number, p.depth + 1,
               p.path_str || ' -> ' || e.source_id
        FROM edges e JOIN path p ON e.source_id = p.target_id
        WHERE p.depth < 10
      )
      SELECT DISTINCT * FROM path WHERE target_id = ? ORDER BY depth LIMIT 20`,
      [source, target]
    );

    if (edges.length === 0) return "No path found.";

    return edges
      .map(
        (e) =>
          `${e.source_id} -> ${e.target_id} (${e.kind}) at ${e.file_path}:${e.line_number} (depth: ${(e as any).depth})`
      )
      .join("\n");
  }

  private callers(args: Record<string, unknown>): string {
    const nodeId = String(args.nodeId || "");
    const depth = Number(args.depth) || 1;

    const edges = this.queryEdges(
      `WITH RECURSIVE callers AS (
        SELECT e.source_id, e.target_id, e.kind, 0 AS depth
        FROM edges e WHERE e.target_id = ?
        UNION ALL
        SELECT e.source_id, e.target_id, e.kind, c.depth + 1
        FROM edges e JOIN callers c ON e.target_id = c.source_id
        WHERE c.depth < ?
      )
      SELECT DISTINCT * FROM callers ORDER BY depth, source_id`,
      [nodeId, depth]
    );

    if (edges.length === 0) return "No callers found.";

    const nodeIds = [...new Set(edges.map((e) => e.source_id))];
    const nodes = nodeIds.length > 0
      ? this.queryNodes(`SELECT * FROM nodes WHERE id IN (${nodeIds.map(() => "?").join(",")})`, nodeIds)
      : [];

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    return edges
      .map((e) => {
        const n = nodeMap.get(e.source_id);
        const label = n ? `${n.name} (${n.kind})` : e.source_id;
        return `${label} via ${e.kind}`;
      })
      .join("\n");
  }

  private callees(args: Record<string, unknown>): string {
    const nodeId = String(args.nodeId || "");
    const depth = Number(args.depth) || 1;

    const edges = this.queryEdges(
      `WITH RECURSIVE callees AS (
        SELECT e.source_id, e.target_id, e.kind, 0 AS depth
        FROM edges e WHERE e.source_id = ?
        UNION ALL
        SELECT e.source_id, e.target_id, e.kind, c.depth + 1
        FROM edges e JOIN callees c ON e.source_id = c.target_id
        WHERE c.depth < ?
      )
      SELECT DISTINCT * FROM callees ORDER BY depth, target_id`,
      [nodeId, depth]
    );

    if (edges.length === 0) return "No callees found.";

    const nodeIds = [...new Set(edges.map((e) => e.target_id))];
    const nodes = nodeIds.length > 0
      ? this.queryNodes(`SELECT * FROM nodes WHERE id IN (${nodeIds.map(() => "?").join(",")})`, nodeIds)
      : [];

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    return edges
      .map((e) => {
        const n = nodeMap.get(e.target_id);
        const label = n ? `${n.name} (${n.kind})` : e.target_id;
        return `${label} via ${e.kind}`;
      })
      .join("\n");
  }

  private impact(args: Record<string, unknown>): string {
    const nodeId = String(args.nodeId || "");
    const depth = Number(args.depth) || 3;

    const edges = this.queryEdges(
      `WITH RECURSIVE impact AS (
        SELECT e.source_id, e.target_id, e.kind, 0 AS depth
        FROM edges e WHERE e.source_id = ? OR e.target_id = ?
        UNION ALL
        SELECT e.source_id, e.target_id, e.kind, i.depth + 1
        FROM edges e JOIN impact i ON (e.source_id = i.target_id OR e.target_id = i.source_id)
        WHERE i.depth < ?
      )
      SELECT DISTINCT * FROM impact ORDER BY depth, source_id, target_id`,
      [nodeId, nodeId, depth]
    );

    if (edges.length === 0) return "No impact found.";

    const nodeIds = [...new Set(edges.flatMap((e) => [e.source_id, e.target_id]))];
    const nodes = nodeIds.length > 0
      ? this.queryNodes(`SELECT * FROM nodes WHERE id IN (${nodeIds.map(() => "?").join(",")})`, nodeIds)
      : [];

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    const byDepth = new Map<number, string[]>();
    for (const e of edges) {
      const d = (e as any).depth as number;
      if (!byDepth.has(d)) byDepth.set(d, []);
      const source = nodeMap.get(e.source_id);
      const target = nodeMap.get(e.target_id);
      const sLabel = source ? `${source.name} (${source.kind})` : e.source_id;
      const tLabel = target ? `${target.name} (${target.kind})` : e.target_id;
      byDepth.get(d)!.push(`${sLabel} -> ${tLabel} (${e.kind})`);
    }

    const lines: string[] = [];
    for (const [d, items] of [...byDepth.entries()].sort(([a], [b]) => a - b)) {
      lines.push(`Depth ${d}:`);
      for (const item of items) lines.push(`  ${item}`);
    }
    return lines.join("\n");
  }

  private node(args: Record<string, unknown>): string {
    const nodeId = String(args.nodeId || "");
    const nodes = this.queryNodes("SELECT * FROM nodes WHERE id = ?", [nodeId]);

    if (nodes.length === 0) return "Node not found.";

    const n = nodes[0];
    let result = `${n.name} (${n.kind})\n`;
    result += `File: ${n.file_path}:${n.line_start}-${n.line_end}\n`;
    result += `Language: ${n.language}\n`;
    if (n.signature) result += `Signature: ${n.signature}\n`;
    if (n.parent_id) result += `Parent: ${n.parent_id}\n`;
    return result;
  }

  private explore(args: Record<string, unknown>): string {
    const query = String(args.query || "");

    const nodes = this.queryNodes(
      "SELECT * FROM nodes WHERE name LIKE ? OR file_path LIKE ? LIMIT 50",
      [`%${query}%`, `%${query}%`]
    );

    if (nodes.length === 0) return "No symbols found.";

    const byFile = new Map<string, NodeRow[]>();
    for (const n of nodes) {
      if (!byFile.has(n.file_path)) byFile.set(n.file_path, []);
      byFile.get(n.file_path)!.push(n);
    }

    const lines: string[] = [];
    for (const [file, fileNodes] of byFile) {
      lines.push(`${file}:`);
      for (const n of fileNodes) {
        lines.push(`  ${n.name} (${n.kind}) :${n.line_start}`);
      }
    }
    return lines.join("\n");
  }

  private status(): string {
    try {
      const nodeCount = (
        this.db.prepare("SELECT COUNT(*) as count FROM nodes").get() as any
      ).count as number;
      const edgeCount = (
        this.db.prepare("SELECT COUNT(*) as count FROM edges").get() as any
      ).count as number;

      let ftsOk = false;
      try {
        this.db.prepare("SELECT count(*) FROM nodes_fts").get();
        ftsOk = true;
      } catch {
        ftsOk = false;
      }

      return JSON.stringify(
        {
          status: "healthy",
          dbPath: this.dbPath,
          nodes: nodeCount,
          edges: edgeCount,
          fts: ftsOk ? "available" : "unavailable",
        },
        null,
        2
      );
    } catch (e) {
      return JSON.stringify({ status: "error", message: String(e) }, null, 2);
    }
  }
}
