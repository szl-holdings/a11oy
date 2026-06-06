// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
//
// js-to-ts-hooks.mjs — ESM resolve hook: maps a relative `.js` specifier to
// its `.ts` sibling when one exists. Lets the widget's bundler-targeted source
// (which writes explicit `.js` import extensions) run directly under
// `node --experimental-strip-types`, with no bundler in the loop.
export async function resolve(specifier, context, nextResolve) {
  if ((specifier.startsWith('./') || specifier.startsWith('../')) && specifier.endsWith('.js')) {
    const tsSpecifier = specifier.slice(0, -3) + '.ts';
    try {
      return await nextResolve(tsSpecifier, context);
    } catch {
      // fall back to the original specifier if no .ts sibling exists
    }
  }
  return nextResolve(specifier, context);
}
