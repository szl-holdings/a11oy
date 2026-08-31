import {
  GovernancePanelsBase,
  makeDarkGoldTheme,
} from '@szl-holdings/szl-doctrine/panels';

const THEME = makeDarkGoldTheme({
  bg: '#0a0a0a',
  cardBg: '#0e0e0e',
  gold: '#c9b787',
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
