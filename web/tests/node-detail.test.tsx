import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import NodeDetail from '@/components/node-detail';

describe('NodeDetail', () => {
  const mockNode = {
    id: 'test.py:MyClass',
    name: 'MyClass',
    kind: 'class',
    file: '/project/test.py',
    line: 10,
    signature: 'class MyClass(BaseModel):',
  };

  it('renders nothing when node is null', () => {
    const { container } = render(<NodeDetail node={null} onClose={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders node name and kind', () => {
    render(<NodeDetail node={mockNode} onClose={vi.fn()} />);
    expect(screen.getByText('MyClass')).toBeInTheDocument();
    expect(screen.getByText('class')).toBeInTheDocument();
  });

  it('renders file path and line number', () => {
    render(<NodeDetail node={mockNode} onClose={vi.fn()} />);
    expect(screen.getByText('/project/test.py:10')).toBeInTheDocument();
  });

  it('renders signature when present', () => {
    render(<NodeDetail node={mockNode} onClose={vi.fn()} />);
    expect(screen.getByText('class MyClass(BaseModel):')).toBeInTheDocument();
  });

  it('renders node ID', () => {
    render(<NodeDetail node={mockNode} onClose={vi.fn()} />);
    expect(screen.getByText('test.py:MyClass')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(<NodeDetail node={mockNode} onClose={onClose} />);
    const closeButton = screen.getByLabelText('Close detail panel');
    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not show signature section when signature is empty', () => {
    const nodeNoSig = { ...mockNode, signature: '' };
    render(<NodeDetail node={nodeNoSig} onClose={vi.fn()} />);
    expect(screen.queryByText('Signature')).not.toBeInTheDocument();
  });
});
