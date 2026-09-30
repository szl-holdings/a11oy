export type ClaimTruthValue = string;

export interface ClaimValue {
  value: string;
  label: string | null;
  truthValue: ClaimTruthValue;
  displayWithLabel: string;
}

/**
 * Offline-safe claim resolver.
 *
 * The standalone Sentra build has no public-claims registry package, so every
 * fallback remains visibly labeled as demo data instead of being presented as
 * a verified production claim.
 */
export function makeClaimResolver(
  _modulePrefix: string,
): (claimId: string, fallback: string) => ClaimValue {
  return function resolveClaim(_claimId: string, fallback: string): ClaimValue {
    return {
      value: fallback,
      label: '[Demo]',
      truthValue: 'pending',
      displayWithLabel: `${fallback} [Demo]`,
    };
  };
}

export function metricDisplay(claimValue: ClaimValue): string {
  return claimValue.displayWithLabel;
}
