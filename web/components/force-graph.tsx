'use client';

import { useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import * as d3 from 'd3';

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  name: string;
  kind: string;
  file: string;
  line: number;
  signature: string;
}

interface GraphEdge {
  source: string | GraphNode;
  target: string | GraphNode;
  kind: string;
}

interface ForceGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onSelectNode: (node: GraphNode | null) => void;
  selectedId: string | null;
}

const KIND_COLORS: Record<string, string> = {
  function: '#f59e0b',
  class: '#3b82f6',
  method: '#8b5cf6',
  interface: '#06b6d4',
  symbol: '#6b7280',
};

export default function ForceGraph({ nodes, edges, onSelectNode, selectedId }: ForceGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  const handleSelect = useCallback((node: GraphNode | null) => {
    onSelectNode(node);
  }, [onSelectNode]);

  useEffect(() => {
    if (!svgRef.current || !nodes.length) return;

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const g = svg.append('g');

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    const linkElements = g.append('g')
      .selectAll<SVGLineElement, GraphEdge>('line')
      .data(edges)
      .join('line')
      .attr('stroke', '#1f1f23')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 1);

    const nodeElements = g.append('g')
      .selectAll<SVGGElement, GraphNode>('g')
      .data(nodes)
      .join('g')
      .style('cursor', 'pointer')
      .attr('data-node-id', (d) => d.id)
      .style('opacity', 0)
      .style('animation', 'node-fade-in 0.3s ease-out forwards')
      .style('animation-delay', (_, i) => `${i * 50}ms`);

    nodeElements.append('circle')
      .attr('r', 6)
      .attr('fill', (d) => KIND_COLORS[d.kind] || '#6b7280')
      .attr('stroke', (d) => d.id === selectedId ? '#2dd4bf' : 'none')
      .attr('stroke-width', (d) => d.id === selectedId ? 2 : 0)
      .attr('data-node-id', (d) => d.id)
      .style('transition', 'r 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), stroke 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), stroke-width 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)');

    nodeElements.append('text')
      .text((d) => d.name)
      .attr('x', 9)
      .attr('y', 4)
      .attr('fill', '#71717a')
      .attr('font-size', '11px')
      .attr('font-family', 'Geist, -apple-system, system-ui, sans-serif')
      .style('pointer-events', 'none');

    const simulation = d3.forceSimulation<GraphNode>(nodes)
      .force('link', d3.forceLink<GraphNode, GraphEdge>(edges).id((d) => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-150))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(12));

    nodeElements.on('click', (_event, d) => {
      handleSelect(d);
    });

    nodeElements.on('mouseenter', function () {
      d3.select(this).select('circle').attr('r', 8);
    }).on('mouseleave', function () {
      d3.select(this).select('circle').attr('r', 6);
    });

    simulation.on('tick', () => {
      linkElements
        .attr('x1', (d: d3.SimulationLinkDatum<GraphNode>) => (d.source as GraphNode).x!)
        .attr('y1', (d: d3.SimulationLinkDatum<GraphNode>) => (d.source as GraphNode).y!)
        .attr('x2', (d: d3.SimulationLinkDatum<GraphNode>) => (d.target as GraphNode).x!)
        .attr('y2', (d: d3.SimulationLinkDatum<GraphNode>) => (d.target as GraphNode).y!);

      nodeElements
        .attr('transform', (d: GraphNode) => `translate(${d.x!},${d.y!})`);
    });

    return () => {
      simulation.stop();
    };
  }, [nodes, edges, selectedId, handleSelect]);

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={nodes.length}
        className="w-full h-full"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
      >
        <svg
          ref={svgRef}
          className="w-full h-full"
          style={{ minHeight: '600px', background: 'var(--color-canvas)' }}
        />
      </motion.div>
    </AnimatePresence>
  );
}
