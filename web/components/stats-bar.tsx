'use client';

import { useEffect, useState } from 'react';
import { motion, animate } from 'framer-motion';

const KIND_COLORS: Record<string, string> = {
  function: '#f59e0b',
  class: '#3b82f6',
  method: '#8b5cf6',
  interface: '#06b6d4',
  symbol: '#6b7280',
};

interface StatsBarProps {
  files: number;
  symbols: number;
  edges: number;
  kindCounts: Record<string, number>;
}

function AnimatedCount({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const controls = animate(0, value, {
      duration: 1.2,
      ease: 'easeOut',
      onUpdate: (v) => setDisplay(Math.round(v)),
    });
    return controls.stop;
  }, [value]);

  return <span data-testid="stat-value">{display}</span>;
}

export default function StatsBar({ files, symbols, edges, kindCounts }: StatsBarProps) {
  const kinds = Object.entries(kindCounts);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className="flex items-center gap-4 px-1"
      style={{ color: 'var(--color-ink-subtle)' }}
    >
      <div className="flex items-center gap-3">
        <span className="text-xs flex items-center gap-1">
          <AnimatedCount value={symbols} />
          <span>symbols</span>
        </span>
        <span className="text-xs" style={{ color: 'var(--color-hairline)' }}>·</span>
        <span className="text-xs flex items-center gap-1">
          <AnimatedCount value={edges} />
          <span>edges</span>
        </span>
        <span className="text-xs" style={{ color: 'var(--color-hairline)' }}>·</span>
        <span className="text-xs flex items-center gap-1">
          <AnimatedCount value={files} />
          <span>files</span>
        </span>
      </div>

      {kinds.length > 0 && (
        <>
          <span className="text-xs" style={{ color: 'var(--color-hairline)' }}>·</span>
          <div className="flex items-center gap-1.5">
            {kinds.map(([kind, count]) => (
              <div
                key={kind}
                className="flex items-center gap-1"
                title={`${count} ${kind}s`}
              >
                <span
                  className="w-2 h-2 rounded-full inline-block"
                  style={{ backgroundColor: KIND_COLORS[kind] || '#6b7280' }}
                />
                <span className="text-xs" style={{ color: 'var(--color-ink-tertiary)' }}>
                  {count}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </motion.div>
  );
}
