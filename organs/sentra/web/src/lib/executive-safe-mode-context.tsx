// VENDORED FROM szl-holdings/platform@e87ad75ec8e280e2fe3a3e8f49c5c0b6c2eec4ea — artifacts/sentra/src/lib/executive-safe-mode-context.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { type ReactNode, createContext, useContext, useState } from 'react';

const LS_KEY = 'executiveSafeMode';

interface ExecutiveSafeModeContextValue {
  safeMode: boolean;
  setSafeMode: (value: boolean) => void;
}

export const ExecutiveSafeModeContext = createContext<ExecutiveSafeModeContextValue>({
  safeMode: false,
  setSafeMode: () => {},
});

export function ExecutiveSafeModeProvider({ children }: { children: ReactNode }) {
  const [safeMode, setSafeModeState] = useState<boolean>(() => {
    try {
      return localStorage.getItem(LS_KEY) === 'true';
    } catch {
      return false;
    }
  });

  function setSafeMode(value: boolean) {
    setSafeModeState(value);
    try {
      localStorage.setItem(LS_KEY, String(value));
    } catch {}
  }

  return (
    <ExecutiveSafeModeContext.Provider value={{ safeMode, setSafeMode }}>
      {children}
    </ExecutiveSafeModeContext.Provider>
  );
}

export function useExecutiveSafeMode(): boolean {
  return useContext(ExecutiveSafeModeContext).safeMode;
}

export function useExecutiveSafeModeToggle(): [boolean, (value: boolean) => void] {
  const { safeMode, setSafeMode } = useContext(ExecutiveSafeModeContext);
  return [safeMode, setSafeMode];
}
