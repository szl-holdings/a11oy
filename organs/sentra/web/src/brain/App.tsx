/**
 * Brain — re-export of the page identifier type used by ROSIE-derived pages.
 *
 * The original ROSIE App.tsx managed its own hash router. Inside Sentra the
 * brain pages are mounted by Sentra's wouter router (see src/pages/brain/),
 * so this file only exports the type contract the pages still depend on.
 */
export type AppPage = 'identity' | 'optimizer' | 'fabric' | 'research' | 'proof' | 'bench';
