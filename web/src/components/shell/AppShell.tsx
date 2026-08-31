import { lazy, Suspense, type ReactNode } from 'react';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import { useFabricShell } from '../../lib/fabric-shell-context';

const EvidenceDrawer = lazy(() =>
  import('@szl-holdings/design-system/cockpit/evidence-drawer').then((m) => ({
    default: m.EvidenceDrawer,
  })),
);

export function AppShell({ children }: { children: ReactNode }) {
  const { drawerOpen, drawerTitle, drawerEvidence, closeEvidenceDrawer } = useFabricShell();

  return (
    <div className="min-h-screen bg-[var(--color-a11oy-navy)] text-[var(--color-a11oy-text)] flex flex-col">
      <TopBar />
      <div className="flex flex-1">
        <Sidebar />
        <main id="main-content" tabIndex={-1} className="flex-1 min-w-0 flex flex-col relative">
          {children}
        </main>
        {drawerOpen && (
          <Suspense fallback={null}>
            <EvidenceDrawer
              open={drawerOpen}
              title={drawerTitle}
              items={drawerEvidence}
              onClose={closeEvidenceDrawer}
            />
          </Suspense>
        )}
      </div>
    </div>
  );
}
