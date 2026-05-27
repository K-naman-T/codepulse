import { describe, it, expect, vi, beforeEach } from "vitest";
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import Database from "better-sqlite3";
import { CodePulseMCPServer } from "../src/mcp.js";

describe("CodePulseMCPServer", () => {
  let tmpDir: string;
  let dbPath: string;
  let server: CodePulseMCPServer;

  function createTestDb(): string {
    const path = join(tmpDir, "graph.db");
    const db = new Database(path);
    db.exec(`
      CREATE TABLE IF NOT EXISTS nodes (
        id TEXT PRIMARY KEY,
        file_path TEXT NOT NULL,
        name TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT '',
        signature TEXT DEFAULT '',
        line_start INTEGER DEFAULT 0,
        line_end INTEGER DEFAULT 0,
        parent_id TEXT,
        language TEXT DEFAULT '',
        metadata TEXT DEFAULT '{}'
      );
      CREATE TABLE IF NOT EXISTS edges (
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        file_path TEXT DEFAULT '',
        line_number INTEGER DEFAULT 0,
        PRIMARY KEY (source_id, target_id, kind)
      );
      CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
        name, signature, file_path, content='nodes', content_rowid='rowid'
      );
    `);
    db.prepare(`
      INSERT INTO nodes (id, file_path, name, kind, signature, line_start, line_end, language)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run("test::main", "/src/main.ts", "main", "function", "function main()", 10, 20, "typescript");
    db.prepare(`
      INSERT INTO nodes (id, file_path, name, kind, signature, line_start, line_end, language)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run("test::helper", "/src/helper.ts", "helper", "function", "function helper()", 5, 15, "typescript");
    db.prepare(`
      INSERT INTO edges (source_id, target_id, kind, file_path, line_number)
      VALUES (?, ?, ?, ?, ?)
    `).run("test::main", "test::helper", "calls", "/src/main.ts", 12);
    db.exec(`
      INSERT INTO nodes_fts (rowid, name, signature, file_path)
      SELECT rowid, name, signature, file_path FROM nodes;
    `);
    db.close();
    return path;
  }

  beforeEach(() => {
    tmpDir = mkdtempSync(join(tmpdir(), "mcp-test-"));
    dbPath = createTestDb();
    server = new CodePulseMCPServer({ dbPath });
  });

  afterEach(() => {
    rmSync(tmpDir, { recursive: true, force: true });
  });

  it("test_server_initializes", () => {
    expect(server).toBeDefined();
  });

  it("test_search_tool", () => {
    const result = server.handleTool("search", { query: "main" });
    expect(result).toContain("main");
  });

  it("test_search_tool_empty", () => {
    const result = server.handleTool("search", { query: "nonexistent" });
    expect(result).toContain("No symbols found");
  });

  it("test_callers_tool", () => {
    const result = server.handleTool("callers", { nodeId: "test::helper" });
    expect(result).toContain("main");
  });

  it("test_callees_tool", () => {
    const result = server.handleTool("callees", { nodeId: "test::main" });
    expect(result).toContain("helper");
  });

  it("test_impact_tool", () => {
    const result = server.handleTool("impact", { nodeId: "test::main" });
    expect(result).toBeTruthy();
  });

  it("test_node_tool", () => {
    const result = server.handleTool("node", { nodeId: "test::main" });
    expect(result).toContain("main");
    expect(result).toContain("function");
  });

  it("test_explore_tool", () => {
    const result = server.handleTool("explore", { query: "main" });
    expect(result).toContain("main");
  });

  it("test_status_tool", () => {
    const result = server.handleTool("status", {});
    expect(result).toContain("healthy");
  });

  it("test_trace_tool", () => {
    const result = server.handleTool("trace", { source: "test::main", target: "test::helper" });
    expect(result).toBeTruthy();
  });

  it("test_context_tool", () => {
    const result = server.handleTool("context", { task: "how does main work" });
    expect(result).toBeTruthy();
  });

  it("test_unknown_tool", () => {
    expect(() => server.handleTool("unknown", {})).toThrow("Unknown tool");
  });
});
