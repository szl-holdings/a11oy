import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, Check, ChevronRight, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { getDomainColor, getSeverityColor } from '../../lib/command/utils';
import type { CommandAction } from '../types';

interface CommandActionsProps {
  actions: CommandAction[];
  onActionResolved?: (id: string) => void;
}

type ActionState = 'pending' | 'confirming' | 'resolving' | 'done' | 'error';

async function resolveAction(id: string): Promise<void> {
  const res = await fetch(`/api/command/actions/${encodeURIComponent(id)}/resolve`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Failed to resolve action: ${res.status}`);
  }
}

export function CommandActions({ actions: serverActions, onActionResolved }: CommandActionsProps) {
  const [localActions, setLocalActions] = useState<CommandAction[]>(serverActions);
  const [states, setStates] = useState<Record<string, ActionState>>({});
  const statesRef = useRef(states);
  statesRef.current = states;

  useEffect(() => {
    setLocalActions((prev) => {
      const currentStates = statesRef.current;
      const inFlightIds = new Set(
        prev
          .filter((a) => {
            const s = currentStates[a.id] ?? 'pending';
            return s === 'confirming' || s === 'resolving';
          })
          .map((a) => a.id),
      );

      const merged = [...serverActions];
      for (const a of prev) {
        if (inFlightIds.has(a.id) && !merged.some((m) => m.id === a.id)) {
          merged.push(a);
        }
      }
      return merged;
    });
  }, [serverActions]);

  const requestConfirm = (id: string) => {
    setStates((prev) => ({ ...prev, [id]: 'confirming' }));
  };

  const cancelConfirm = (id: string) => {
    setStates((prev) => ({ ...prev, [id]: 'pending' }));
  };

  const confirm = async (id: string) => {
    setStates((prev) => ({ ...prev, [id]: 'resolving' }));
    try {
      await resolveAction(id);
      setStates((prev) => ({ ...prev, [id]: 'done' }));
      onActionResolved?.(id);
      setTimeout(() => {
        setLocalActions((prev) => prev.filter((a) => a.id !== id));
        setStates((prev) => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
      }, 1500);
    } catch {
      setStates((prev) => ({ ...prev, [id]: 'error' }));
      setTimeout(() => {
        setStates((prev) => ({ ...prev, [id]: 'pending' }));
      }, 2000);
    }
  };

  if (localActions.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <h2
          className="text-xs font-bold tracking-widest uppercase px-1"
          style={{ color: 'var(--color-fg-muted)' }}
        >
          Required Actions
        </h2>
        <div
          className="p-4 rounded-lg border text-sm text-center"
          style={{
            backgroundColor: 'var(--color-surface-base)',
            borderColor: 'var(--color-surface-border)',
            color: 'var(--color-fg-muted)',
          }}
        >
          All actions resolved
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <h2
        className="text-xs font-bold tracking-widest uppercase px-1"
        style={{ color: 'var(--color-fg-muted)' }}
      >
        Required Actions
      </h2>
      <div className="flex flex-col gap-2">
        <AnimatePresence>
          {localActions.map((action) => {
            const state: ActionState = states[action.id] ?? 'pending';
            const severityColor = getSeverityColor(action.priority);
            const domainColor = getDomainColor(action.domain);
            const isInFlight = state === 'resolving';

            return (
              <motion.div
                key={action.id}
                initial={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0, marginBottom: 0, overflow: 'hidden' }}
                transition={{ duration: 0.3 }}
                className="rounded-lg border"
                style={{
                  backgroundColor: 'var(--color-surface-base)',
                  borderColor:
                    state === 'confirming' || state === 'resolving'
                      ? severityColor
                      : state === 'error'
                        ? 'var(--color-critical)'
                        : 'var(--color-surface-border)',
                }}
                data-testid={`action-item-${action.id}`}
              >
                <div className="flex items-center justify-between gap-4 p-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className="w-1 h-8 rounded-full shrink-0"
                      style={{ backgroundColor: severityColor }}
                    />
                    <div className="flex flex-col gap-0.5 min-w-0">
                      <span
                        className="text-[10px] font-mono uppercase tracking-wider"
                        style={{ color: domainColor }}
                      >
                        {action.domain.toUpperCase()} / {action.priority}
                      </span>
                      <span
                        className="text-sm font-medium truncate"
                        style={{ color: 'var(--color-fg-primary)' }}
                      >
                        {action.text}
                      </span>
                    </div>
                  </div>

                  <div className="shrink-0 flex items-center gap-2">
                    {state === 'done' ? (
                      <div
                        className="flex items-center gap-2 px-3 py-1.5 rounded-md border text-xs font-bold uppercase tracking-wide"
                        style={{
                          color: 'var(--color-low)',
                          backgroundColor: 'color-mix(in srgb, var(--color-low) 10%, transparent)',
                          borderColor: 'color-mix(in srgb, var(--color-low) 25%, transparent)',
                        }}
                      >
                        <Check className="w-4 h-4" />
                        Done
                      </div>
                    ) : state === 'error' ? (
                      <div
                        className="px-3 py-1.5 rounded-md text-xs font-bold uppercase tracking-wide"
                        style={{
                          color: 'var(--color-critical)',
                          backgroundColor:
                            'color-mix(in srgb, var(--color-critical) 10%, transparent)',
                        }}
                      >
                        Failed — retry
                      </div>
                    ) : state === 'confirming' || state === 'resolving' ? (
                      <>
                        <div
                          className="flex items-center gap-1.5 text-xs font-medium"
                          style={{ color: severityColor }}
                        >
                          <AlertTriangle className="w-3.5 h-3.5" />
                          Confirm?
                        </div>
                        <button
                          onClick={() => cancelConfirm(action.id)}
                          disabled={isInFlight}
                          className="px-3 py-1.5 text-xs font-bold uppercase tracking-wide rounded-md border transition-colors disabled:opacity-40"
                          style={{
                            color: 'var(--color-fg-muted)',
                            borderColor: 'var(--color-surface-border)',
                            backgroundColor: 'transparent',
                          }}
                          data-testid={`button-cancel-${action.id}`}
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => confirm(action.id)}
                          disabled={isInFlight}
                          className="px-3 py-1.5 text-xs font-bold uppercase tracking-wide rounded-md transition-colors disabled:opacity-60"
                          style={{
                            backgroundColor: isInFlight
                              ? 'var(--color-surface-border)'
                              : severityColor,
                            color: isInFlight ? 'var(--color-fg-muted)' : 'hsl(210 12% 5%)',
                          }}
                          data-testid={`button-confirm-${action.id}`}
                        >
                          {isInFlight ? '...' : action.buttonText}
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => requestConfirm(action.id)}
                        className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider px-4 py-1.5 rounded-md transition-colors"
                        style={{
                          backgroundColor: 'var(--color-fg-primary)',
                          color: 'var(--color-bg-primary)',
                        }}
                        data-testid={`button-action-${action.id}`}
                      >
                        {action.buttonText}
                        <ChevronRight className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
