/**
 * Copyright 2026 SZL Holdings
 * SPDX-License-Identifier: Apache-2.0
 *
 * SZL Receipt Policy — Pepr Module entry point
 *
 * This module registers a single capability: szlReceiptPolicy.
 * It watches Deployment and Job resources cluster-wide and, on each
 * admission event, generates a DSSE-wrapped HMAC-SHA-256 receipt and
 * POSTs it to the in-cluster SZL receipts server.
 *
 * Design goals:
 *   - Zero coupling to uds-core internals: communicates only over the network
 *   - AGPL-safe: this module is Apache-2.0 and contains no AGPL code
 *   - Contributable to the Defense Unicorns ecosystem as-is
 *
 * References:
 *   Pepr module pattern: https://github.com/defenseunicorns/uds-core/blob/main/pepr.ts
 *   Pepr docs: https://docs.pepr.dev
 */

import { PeprModule } from "pepr";
import cfg from "./package.json";
import { szlReceiptPolicy } from "./policies/szl-receipt-on-deploy";

new PeprModule(cfg, [szlReceiptPolicy]);
