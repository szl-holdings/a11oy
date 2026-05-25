import {
  GovernancePanelsBase,
  makeDarkGoldTheme,
} from '@szl-holdings/szl-doctrine/panels';
import {
  LEAN_DECLARATIONS,
  PACKAGE_INVENTORY,
} from '@szl-holdings/szl-doctrine';

const THEME = makeDarkGoldTheme({
  bg: '#0a0a0a',
  cardBg: '#0e0e0e',
  gold: '#c9b787',
});

export function A11oyGovernancePanels() {
  return (
    <GovernancePanelsBase
      slug="a11oy"
      theme={THEME}
      headline="Brand orchestration — every decision crosses the Λ gate before it ships"
      extraOwnershipRows={[
        {
          label: 'Operator console',
          value: '/a11oy/command/* · /command/* alias',
        },
        {
          label: 'Workspace packages',
          value: `${PACKAGE_INVENTORY.workspacePackageCount} · ${PACKAGE_INVENTORY.orgRepoCount} org repos`,
        },
        {
          label: 'Payload size',
          value: `${PACKAGE_INVENTORY.payloadFileCount} files · ${(PACKAGE_INVENTORY.payloadByteCount / 1_048_576).toFixed(2)} MiB`,
        },
        {
          label: 'Lean TH8 · axioms / theorems',
          value: `${LEAN_DECLARATIONS.axioms} axioms · ${LEAN_DECLARATIONS.theorems} theorems`,
          mono: true,
        },
        {
          label: 'Lean TH8 · defs / lemmas',
          value: `${LEAN_DECLARATIONS.definitions} defs · ${LEAN_DECLARATIONS.lemmas} lemmas · ${LEAN_DECLARATIONS.bareSorryCount} bare sorry`,
          mono: true,
        },
        {
          label: 'TH8 · derivations',
          value: `${LEAN_DECLARATIONS.derivations} obligations · ${LEAN_DECLARATIONS.derivationsClosed} closed · ${LEAN_DECLARATIONS.derivationsSkeleton} skeleton · ${LEAN_DECLARATIONS.derivationsBlocked} blocked`,
          mono: true,
        },
      ]}
    />
  );
}
