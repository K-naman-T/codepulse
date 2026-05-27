import Database from 'better-sqlite3';
import path from 'path';
import os from 'os';

let db: Database.Database | null = null;

export function getDb(dbPath?: string): Database.Database {
  if (db) return db;
  const resolved = dbPath || process.env.CODEPULSE_DB_PATH || path.join(os.homedir(), '.codepulse', 'graph.db');
  db = new Database(resolved);
  db.pragma('journal_mode = WAL');
  return db;
}

export interface Node {
  id: string;
  file_path: string;
  name: string;
  kind: string;
  signature: string;
  line_start: number;
  line_end: number;
  parent_id: string | null;
  language: string;
}

export interface Edge {
  id: number;
  source_id: string;
  target_id: string;
  kind: string;
  file_path: string;
  line_number: number;
}

export interface GraphData {
  nodes: { id: string; name: string; kind: string; file: string; line: number; signature: string }[];
  edges: { source: string; target: string; kind: string }[];
}
