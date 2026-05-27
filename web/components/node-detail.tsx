'use client';

import { motion } from 'framer-motion';
import { X } from '@phosphor-icons/react';

interface NodeData {
  id: string;
  name: string;
  kind: string;
  file: string;
  line: number;
  signature: string;
}

interface NodeDetailProps {
  node: NodeData | null;
  onClose: () => void;
}

const KIND_COLORS: Record<string, string> = {
  function: '#f59e0b',
  class: '#3b82f6',
  method: '#8b5cf6',
  interface: '#06b6d4',
  symbol: '#6b7280',
};

export default function NodeDetail({ node, onClose }: NodeDetailProps) {
  if (!node) return null;

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="rounded-lg border"
      style={{
        backgroundColor: 'var(--color-surface-1)',
        borderColor: 'var(--color-hairline)',
        padding: 'var(--spacing-lg)',
      }}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          <span
            className="w-2.5 h-2.5 rounded-full inline-block"
            style={{ backgroundColor: KIND_COLORS[node.kind] || '#6b7280' }}
          />
          <h3
            className="text-base font-semibold"
            style={{ color: 'var(--color-ink)' }}
          >
            {node.name}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md transition-colors hover:opacity-80"
          style={{ color: 'var(--color-ink-muted)' }}
          aria-label="Close detail panel"
        >
          <X size={16} weight="bold" />
        </button>
      </div>

      <div className="mb-3">
        <span
          className="inline-block px-2 py-0.5 text-xs font-medium rounded-full"
          style={{
            backgroundColor: `${KIND_COLORS[node.kind] || '#6b7280'}20`,
            color: KIND_COLORS[node.kind] || '#6b7280',
          }}
        >
          {node.kind}
        </span>
      </div>

      <div className="space-y-2">
        <div>
          <p
            className="text-xs font-medium mb-1"
            style={{ color: 'var(--color-ink-subtle)' }}
          >
            File
          </p>
          <p
            className="text-sm"
            style={{
              color: 'var(--color-ink-muted)',
              fontFamily: 'Geist Mono, ui-monospace, monospace',
            }}
          >
            {node.file}:{node.line}
          </p>
        </div>

        {node.signature && (
          <div>
            <p
              className="text-xs font-medium mb-1"
              style={{ color: 'var(--color-ink-subtle)' }}
            >
              Signature
            </p>
            <p
              className="text-sm"
              style={{
                color: 'var(--color-ink-muted)',
                fontFamily: 'Geist Mono, ui-monospace, monospace',
              }}
            >
              {node.signature}
            </p>
          </div>
        )}

        <div>
          <p
            className="text-xs font-medium mb-1"
            style={{ color: 'var(--color-ink-subtle)' }}
          >
            ID
          </p>
          <p
            className="text-xs"
            style={{
              color: 'var(--color-ink-tertiary)',
              fontFamily: 'Geist Mono, ui-monospace, monospace',
              wordBreak: 'break-all',
            }}
          >
            {node.id}
          </p>
        </div>
      </div>
    </motion.div>
  );
}
