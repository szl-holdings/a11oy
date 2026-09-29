import {
  GovernancePanelsBase,
  makeDarkGoldTheme,
} from '@szl-holdings/szl-doctrine/panels';

const THEME = makeDarkGoldTheme({
  bg: 'var(--bg)',
  cardBg: 'var(--bg-deep)',
  gold: 'var(--text-sub)',
});

export function ConduitGovernancePanels() {
  return (
    <GovernancePanelsBase
      slug="conduit"
      theme={THEME}
      headline="Amaru ouroboros — closure → category → confluence holds end-to-end"
      doctrineAnatomyHref="https://a11oy.szlholdings.com/doctrine/anatomy"
    />
  );
}
