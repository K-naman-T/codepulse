'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { MagnifyingGlass, Graph, XCircle, ArrowsClockwise } from '@phosphor-icons/react';
import { motion } from 'framer-motion';
import ForceGraph from '@/components/force-graph';
import NodeDetail from '@/components/node-detail';
import StatsBar from '@/components/stats-bar';

interface GraphNode {
  id: string;
  name: string;
  kind: string;
  file: string;
  line: number;
  signature: string;
}

interface GraphEdge {
  source: string;
  target: string;
  kind: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export default function Home() {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [stats, setStats] = useState({ files: 0, symbols: 0, edges: 0 });
  const [kindCounts, setKindCounts] = useState<Record<string, number>>({});
  const searchRef = useRef<HTMLInputElement>(null);

  const fetchGraph = useCallback(async (query?: string) => {
    setLoading(true);
    setError(null);
    try {
      const url = query
        ? `/api/search?q=${encodeURIComponent(query)}`
        : '/api/graph';

      const res = await fetch(url);
      if (!res.ok) throw new Error(await res.text());

      if (query) {
        const nodes: GraphNode[] = await res.json();
        setData({ nodes, edges: [] });
      } else {
        const graph: GraphData = await res.json();
        setData(graph);
        const files = new Set(graph.nodes.map((n) => n.file));
        setStats({ files: files.size, symbols: graph.nodes.length, edges: graph.edges.length });
        const counts: Record<string, number> = {};
        graph.nodes.forEach((n) => {
          counts[n.kind] = (counts[n.kind] || 0) + 1;
        });
        setKindCounts(counts);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchGraph();
  }, [fetchGraph]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchGraph(searchQuery.trim() || undefined);
  };

  const clearSearch = () => {
    setSearchQuery('');
    fetchGraph();
    searchRef.current?.focus();
  };

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      searchRef.current?.focus();
    }
    if (e.key === 'Escape') {
      if (searchQuery) {
        setSearchQuery('');
        fetchGraph();
      } else {
        setSelectedNode(null);
      }
      searchRef.current?.blur();
    }
    if (e.key === 'r' && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const active = document.activeElement;
      if (active && active.tagName === 'INPUT') return;
      e.preventDefault();
      fetchGraph();
    }
  }, [searchQuery, fetchGraph]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: 'var(--color-canvas)' }}
    >
      <header
        className="flex items-center justify-between px-6"
        style={{
          height: '56px',
          borderBottom: '1px solid var(--color-hairline)',
          backgroundColor: 'var(--color-canvas)',
        }}
      >
        <div className="flex items-center gap-3">
          <Graph size={20} weight="bold" style={{ color: 'var(--color-primary)' }} />
          <span
            className="font-semibold text-sm tracking-tight"
            style={{ color: 'var(--color-ink)' }}
          >
            CodePulse
          </span>
          <span
            className="text-xs px-1.5 py-0.5 rounded hidden sm:inline-block"
            style={{ backgroundColor: 'var(--color-surface-2)', color: 'var(--color-ink-tertiary)' }}
          >
            Ctrl+K
          </span>
        </div>

        <form onSubmit={handleSearch} className="relative flex items-center">
          <MagnifyingGlass
            size={14}
            weight="bold"
            className="absolute left-3"
            style={{ color: 'var(--color-ink-subtle)' }}
          />
          <input
            ref={searchRef}
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search symbols..."
            className="pl-8 pr-8 py-1.5 text-sm rounded-md border transition-colors"
            style={{
              backgroundColor: 'var(--color-surface-1)',
              color: 'var(--color-ink)',
              borderColor: 'var(--color-hairline)',
              width: '280px',
            }}
          />
          {searchQuery && (
            <button
              type="button"
              onClick={clearSearch}
              className="absolute right-2 p-0.5"
              style={{ color: 'var(--color-ink-subtle)' }}
            >
              <XCircle size={14} weight="fill" />
            </button>
          )}
        </form>
      </header>

      <main className="flex-1 flex gap-4 p-4 max-w-[1400px] mx-auto w-full">
        <div className="flex-1 flex flex-col">
          <div
            className="flex-1 rounded-xl border relative"
            style={{
              borderColor: 'var(--color-hairline)',
              backgroundColor: 'var(--color-canvas)',
              minHeight: '70vh',
            }}
          >
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                className="m-4 px-4 py-3 rounded-lg text-sm flex items-center gap-2"
                style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  color: 'var(--color-semantic-error)',
                }}
              >
                <span>{error}</span>
                <button onClick={() => fetchGraph()} className="underline ml-auto flex items-center gap-1">
                  <ArrowsClockwise size={14} weight="bold" />
                  Retry
                </button>
              </motion.div>
            )}

            {loading && (
              <div className="absolute inset-0 flex flex-col gap-3 p-6">
                <div className="flex-1 rounded-lg animate-skeleton" style={{ backgroundColor: 'var(--color-surface-2)' }} />
                <div className="flex gap-3">
                  <div className="h-3 w-20 rounded animate-skeleton" style={{ backgroundColor: 'var(--color-surface-2)' }} />
                  <div className="h-3 w-16 rounded animate-skeleton" style={{ backgroundColor: 'var(--color-surface-2)' }} />
                  <div className="h-3 w-14 rounded animate-skeleton" style={{ backgroundColor: 'var(--color-surface-2)' }} />
                </div>
              </div>
            )}

            {!loading && data && data.nodes.length > 0 && (
              <ForceGraph
                nodes={data.nodes}
                edges={data.edges}
                onSelectNode={setSelectedNode}
                selectedId={selectedNode?.id || null}
              />
            )}

            {!loading && !error && (!data || data.nodes.length === 0) && (
              <div className="flex items-center justify-center h-full" style={{ color: 'var(--color-ink-muted)' }}>
                <div className="text-center">
                  <Graph size={32} weight="thin" className="mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No data indexed yet.</p>
                  <p className="text-xs mt-1" style={{ color: 'var(--color-ink-tertiary)' }}>
                    Run <code className="px-1 rounded" style={{ backgroundColor: 'var(--color-surface-1)' }}>codepulse index</code> to build the graph
                  </p>
                </div>
              </div>
            )}
          </div>

          {data && data.nodes.length > 0 && (
            <div className="mt-3">
              <StatsBar
                files={stats.files}
                symbols={stats.symbols}
                edges={stats.edges}
                kindCounts={kindCounts}
              />
            </div>
          )}
        </div>

        <aside className="w-80 shrink-0 hidden lg:block">
          {selectedNode ? (
            <NodeDetail node={selectedNode} onClose={() => setSelectedNode(null)} />
          ) : (
            <div
              className="rounded-lg border"
              style={{
                backgroundColor: 'var(--color-surface-1)',
                borderColor: 'var(--color-hairline)',
                padding: 'var(--spacing-lg)',
              }}
            >
              <h4
                className="text-xs font-semibold mb-3 uppercase tracking-wider"
                style={{ color: 'var(--color-ink-muted)' }}
              >
                Legend
              </h4>
              <div className="space-y-2">
                {[
                  { kind: 'function', color: 'var(--color-node-function)' },
                  { kind: 'class', color: 'var(--color-node-class)' },
                  { kind: 'method', color: 'var(--color-node-method)' },
                  { kind: 'interface', color: 'var(--color-node-interface)' },
                ].map(({ kind, color }) => (
                  <div key={kind} className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full inline-block shrink-0"
                      style={{ backgroundColor: color }}
                    />
                    <span className="text-sm capitalize" style={{ color: 'var(--color-ink-muted)' }}>
                      {kind}
                    </span>
                  </div>
                ))}
              </div>
              <p className="text-xs mt-4" style={{ color: 'var(--color-ink-tertiary)' }}>
                Click a node to see details.
              </p>
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}
