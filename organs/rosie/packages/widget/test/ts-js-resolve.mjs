// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
//
// ts-js-resolve.mjs — registration entry. Installs js-to-ts-hooks.mjs as an
// ESM customization hook so it runs under node's synchronous resolver (used by
// --experimental-strip-types). Pass via --import:
//   node --experimental-strip-types --import ./test/ts-js-resolve.mjs --test ...
import { register } from 'node:module';
import { pathToFileURL } from 'node:url';
register('./js-to-ts-hooks.mjs', pathToFileURL(import.meta.dirname + '/'));
