import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/db';

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.get('q') || '';
  const kind = request.nextUrl.searchParams.get('kind') || '';

  try {
    const db = getDb();

    let sql: string;
    let params: any[];

    if (query.trim()) {
      sql = `SELECT n.* FROM nodes n
             JOIN nodes_fts fts ON n.rowid = fts.rowid
             WHERE nodes_fts MATCH ?`;
      params = [query + '*'];
      if (kind) {
        sql += ' AND n.kind = ?';
        params.push(kind);
      }
      sql += ' ORDER BY rank LIMIT 50';
    } else {
      sql = 'SELECT * FROM nodes';
      params = [];
      if (kind) {
        sql += ' WHERE kind = ?';
        params.push(kind);
      }
      sql += ' ORDER BY name LIMIT 50';
    }

    const nodes = db.prepare(sql).all(...params);
    return NextResponse.json(nodes);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
