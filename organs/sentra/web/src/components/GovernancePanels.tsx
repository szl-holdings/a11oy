import {
  GovernancePanelsBase,
  makeDarkGoldTheme,
} from '@szl-holdings/szl-doctrine/panels';

const THEME = makeDarkGoldTheme({
  bg: '#0a0a0a',
  cardBg: '#0e0e0e',
  gold: '#c9b787',
});

export function SentraGovernancePanels() {
  return (
    <GovernancePanelsBase
      slug="sentra"
      theme={THEME}
      headline="Cyber resilience — every alert carries its proof envelope"
      doctrineAnatomyHref="https://a11oy.szlholdings.com/doctrine/anatomy"
    />
  );
}
