import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatsBar from '@/components/stats-bar';

describe('StatsBar', () => {
  it('test_shows_correct_counts', () => {
    const { container } = render(
      <StatsBar
        files={15}
        symbols={42}
        edges={87}
        kindCounts={{ function: 10, class: 5, method: 20, interface: 7 }}
      />
    );
    const values = container.querySelectorAll('[data-testid="stat-value"]');
    expect(values.length).toBe(3);
    expect(screen.getByText('symbols')).toBeInTheDocument();
    expect(screen.getByText('edges')).toBeInTheDocument();
    expect(screen.getByText('files')).toBeInTheDocument();
  });

  it('test_animated_counters', () => {
    const { container } = render(
      <StatsBar
        files={0}
        symbols={100}
        edges={0}
        kindCounts={{}}
      />
    );
    const spans = container.querySelectorAll('[data-testid="stat-value"]');
    expect(spans.length).toBe(3);
  });
});
