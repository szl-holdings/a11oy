// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
//
// Runtime entry. `cloudflare:email` exists only in workerd, so all logic lives
// in handler.mjs and receives the EmailMessage class by injection; Node tests
// pass a recording stand-in and test/workerd/ runs this file in workerd.

import { EmailMessage } from "cloudflare:email";

import { handleRequest } from "./handler.mjs";

export default {
  fetch(request, env) {
    return handleRequest(request, env, { EmailMessage });
  },
};
