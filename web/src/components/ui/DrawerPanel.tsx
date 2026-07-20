// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — artifacts/a11oy/src/components/ui/DrawerPanel.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@szl-holdings/design-system';

interface DrawerPanelProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  width?: string;
}

export function DrawerPanel({ isOpen, onClose, title, subtitle, children, width = 'w-[480px]' }: DrawerPanelProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-[var(--color-a11oy-navy)]/50 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className={cn(
              "fixed top-0 right-0 bottom-0 z-50 bg-[var(--color-a11oy-card)] border-l border-[var(--color-a11oy-border)] shadow-2xl flex flex-col",
              width
            )}
          >
            <div className="flex items-start justify-between p-6 border-b border-[var(--color-a11oy-border)]">
              <div>
                <h2 className="text-lg font-medium text-[var(--color-a11oy-text)]">{title}</h2>
                {subtitle && <p className="text-sm text-[var(--color-a11oy-text-sub)] mt-1">{subtitle}</p>}
              </div>
              <button 
                onClick={onClose}
                className="p-2 -mr-2 text-[var(--color-a11oy-text-ghost)] hover:text-[var(--color-a11oy-text)] transition-colors rounded-full hover:bg-[var(--color-a11oy-surface)]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              {children}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
