// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — artifacts/sentra/src/lib/use-step-up.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { useCallback } from 'react';

let tokenCounter = 0;

function generateStepUpToken(): string {
  tokenCounter++;
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 8);
  return `step-up-${ts}-${rand}-${tokenCounter}`;
}

export function useStepUp() {
  const requestStepUp = useCallback((actionDescription: string): Promise<string | null> => {
    return new Promise((resolve) => {
      const confirmed = window.confirm(
        `⚠ STEP-UP VERIFICATION REQUIRED\n\nAction: ${actionDescription}\n\nThis is a sensitive operation that requires explicit operator confirmation.\n\nProceed?`,
      );
      if (confirmed) {
        resolve(generateStepUpToken());
      } else {
        resolve(null);
      }
    });
  }, []);

  return { requestStepUp };
}
