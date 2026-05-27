import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import Home from '@/app/page';

describe('Page states', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('test_loading_shows_skeleton', () => {
    global.fetch = vi.fn(() => new Promise(() => {}));
    render(<Home />);
    const skeleton = document.querySelector('.animate-skeleton');
    expect(skeleton).toBeInTheDocument();
  });

  it('test_empty_shows_cli_hint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ nodes: [], edges: [] }),
      text: () => Promise.resolve(''),
    });
    render(<Home />);
    await waitFor(() => {
      expect(screen.getByText(/No data indexed/)).toBeInTheDocument();
    });
  });

  it('test_error_shows_retry', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('boom'));
    render(<Home />);
    await waitFor(() => {
      expect(screen.getByText(/Retry/)).toBeInTheDocument();
    });
  });
});
