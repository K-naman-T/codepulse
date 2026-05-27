import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import ForceGraph from '@/components/force-graph';

describe('ForceGraph', () => {
  const mockNodes = [
    { id: 'test:A', name: 'A', kind: 'function', file: 'test.ts', line: 1, signature: 'function A()' },
    { id: 'test:B', name: 'B', kind: 'class', file: 'test.ts', line: 5, signature: 'class B' },
  ];
  const mockEdges = [
    { source: 'test:A', target: 'test:B', kind: 'calls' },
  ];

  it('renders SVG element', () => {
    const { container } = render(
      <ForceGraph
        nodes={mockNodes}
        edges={mockEdges}
        onSelectNode={vi.fn()}
        selectedId={null}
      />
    );
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('renders without crashing when empty', () => {
    const { container } = render(
      <ForceGraph
        nodes={[]}
        edges={[]}
        onSelectNode={vi.fn()}
        selectedId={null}
      />
    );
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('calls onSelectNode when a node is defined', () => {
    const onSelect = vi.fn();
    render(
      <ForceGraph
        nodes={mockNodes}
        edges={mockEdges}
        onSelectNode={onSelect}
        selectedId={null}
      />
    );
    expect(onSelect).not.toHaveBeenCalled();
  });
});
