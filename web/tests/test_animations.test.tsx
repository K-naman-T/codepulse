import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import ForceGraph from '@/components/force-graph';

describe('ForceGraph animations', () => {
  const mockNodes = [
    { id: 'test:A', name: 'A', kind: 'function', file: 'test.ts', line: 1, signature: 'function A()' },
    { id: 'test:B', name: 'B', kind: 'class', file: 'test.ts', line: 5, signature: 'class B' },
  ];
  const mockEdges = [{ source: 'test:A', target: 'test:B', kind: 'calls' }];

  it('test_node_hover_scale', () => {
    const { container } = render(
      <ForceGraph
        nodes={mockNodes}
        edges={mockEdges}
        onSelectNode={vi.fn()}
        selectedId={null}
      />
    );
    const circles = container.querySelectorAll('svg circle');
    expect(circles.length).toBe(2);
    circles.forEach((circle) => {
      expect(circle.getAttribute('r')).toBe('6');
    });
  });

  it('test_node_click_teal_stroke', () => {
    const { container } = render(
      <ForceGraph
        nodes={mockNodes}
        edges={mockEdges}
        onSelectNode={vi.fn()}
        selectedId="test:A"
      />
    );
    const circle = container.querySelector('circle[data-node-id="test:A"]');
    expect(circle).toBeTruthy();
    expect(circle!.getAttribute('stroke')).toBe('#2dd4bf');
    expect(circle!.getAttribute('stroke-width')).toBe('2');
  });

  it('test_staggered_mount', () => {
    const { container } = render(
      <ForceGraph
        nodes={mockNodes}
        edges={mockEdges}
        onSelectNode={vi.fn()}
        selectedId={null}
      />
    );
    const nodeEls = container.querySelectorAll('circle[data-node-id]');
    expect(nodeEls.length).toBe(2);
  });
});
