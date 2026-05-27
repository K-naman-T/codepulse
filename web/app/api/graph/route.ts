import { NextResponse } from 'next/server';
import { getDb, GraphData } from '@/lib/db';

export async function GET() {
  try {
    const db = getDb();
    const nodes = db.prepare('SELECT id, name, kind, file_path, line_start, signature FROM nodes ORDER BY name').all() as any[];
    const edges = db.prepare('SELECT source_id, target_id, kind FROM edges').all() as any[];

    const data: GraphData = {
      nodes: nodes.map((n: any) => ({
        id: n.id,
        name: n.name,
        kind: n.kind,
        file: n.file_path,
        line: n.line_start,
        signature: n.signature || '',
      })),
      edges: edges.map((e: any) => ({
        source: e.source_id,
        target: e.target_id,
        kind: e.kind,
      })),
    };

    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
