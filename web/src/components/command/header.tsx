import { Activity, GitCompareArrows, LayoutGrid, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'wouter';

interface HeaderProps {
  lastUpdatedAt: number;
  sseConnected?: boolean;
  onSearchOpen?: () => void;
  onAppSwitcherOpen?: () => void;
}

export function Header({
  lastUpdatedAt,
  sseConnected = false,
  onSearchOpen,
  onAppSwitcherOpen,
}: HeaderProps) {
  const [time, setTime] = useState(new Date());
  const [countdown, setCountdown] = useState(30);

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    setCountdown(30);
    if (sseConnected) return;
    const interval = setInterval(() => {
      setCountdown((prev) => (prev <= 1 ? 30 : prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [lastUpdatedAt, sseConnected]);

  return (
    <header
      className="flex items-center justify-between px-6 py-4 sticky top-0 z-50"
      style={{
        backgroundColor: 'var(--color-bg-primary)',
        borderBottom: '1px solid var(--color-surface-border)',
      }}
    >
      <div className="flex items-center gap-3">
        <Activity className="w-5 h-5" style={{ color: 'var(--color-fg-muted)' }} />
        <h1
          className="text-sm font-bold tracking-[0.2em]"
          style={{ color: 'var(--color-fg-primary)' }}
        >
          ECOSYSTEM COMMAND
        </h1>
      </div>

      <div className="flex items-center gap-4">
        {onAppSwitcherOpen && (
          <button
            onClick={onAppSwitcherOpen}
            className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs transition-colors"
            style={{
              backgroundColor: 'var(--color-surface-base)',
              border: '1px solid var(--color-surface-border)',
              color: 'var(--color-fg-muted)',
            }}
            aria-label="Open app switcher"
            title="Switch to any platform app (⌘J)"
          >
            <LayoutGrid className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Apps</span>
            <kbd
              className="hidden sm:inline text-[10px] px-1 rounded"
              style={{
                backgroundColor: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-surface-border)',
                color: 'var(--color-fg-muted)',
              }}
            >
              ⌘J
            </kbd>
          </button>
        )}
        {onSearchOpen && (
          <button
            onClick={onSearchOpen}
            className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs transition-colors"
            style={{
              backgroundColor: 'var(--color-surface-base)',
              border: '1px solid var(--color-surface-border)',
              color: 'var(--color-fg-muted)',
            }}
            aria-label="Open search"
          >
            <Search className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Search</span>
            <kbd
              className="hidden sm:inline text-[10px] px-1 rounded"
              style={{
                backgroundColor: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-surface-border)',
                color: 'var(--color-fg-muted)',
              }}
            >
              ⌘K
            </kbd>
          </button>
        )}

        <Link
          href="/operations/what-changed"
          className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-md text-xs transition-all hover:opacity-80"
          style={{
            backgroundColor: 'color-mix(in srgb, #8b7ac8 8%, var(--color-surface-base))',
            border: '1px solid color-mix(in srgb, #8b7ac8 25%, var(--color-surface-border))',
            color: '#a78bfa',
          }}
          title="See what changed since you last viewed"
        >
          <GitCompareArrows className="w-3.5 h-3.5" />
          <span>What Changed</span>
        </Link>

        <div
          className="flex items-center gap-6 text-xs font-mono"
          style={{ color: 'var(--color-fg-muted)' }}
        >
          {sseConnected ? (
            <div className="flex items-center gap-2">
              <span
                className="w-2 h-2 rounded-full"
                style={{
                  backgroundColor: 'var(--color-low)',
                  boxShadow: '0 0 6px var(--color-low)',
                }}
              />
              <span style={{ color: 'var(--color-low)' }}>LIVE</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span
                className="w-2 h-2 rounded-full animate-pulse"
                style={{ backgroundColor: 'var(--color-aegis)' }}
              />
              <span>Refreshing in: {countdown}s</span>
            </div>
          )}
          <div className="hidden md:block">
            {time.toISOString().replace('T', ' ').substring(0, 19)} UTC
          </div>
        </div>
      </div>
    </header>
  );
}
