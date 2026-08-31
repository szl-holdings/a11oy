import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

export type OrgId = 'szl' | 'acme' | 'northwind';

interface OrgContextType {
  currentOrg: OrgId;
  setOrg: (org: OrgId) => void;
}

const OrgContext = createContext<OrgContextType | undefined>(undefined);

export function OrgProvider({ children }: { children: ReactNode }) {
  const [currentOrg, setOrg] = useState<OrgId>('szl');

  return (
    <OrgContext.Provider value={{ currentOrg, setOrg }}>
      {children}
    </OrgContext.Provider>
  );
}

export function useOrg() {
  const context = useContext(OrgContext);
  if (context === undefined) {
    throw new Error('useOrg must be used within an OrgProvider');
  }
  return context;
}
