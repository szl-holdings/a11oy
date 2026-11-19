/* SPDX-License-Identifier: Apache-2.0
 * Shows which build is running: reads the read-only /api/build endpoint and
 * writes the release id into the szl-release-id meta tag and the footer.
 * Contains no build ids itself (so the bundle hash has no circular dependency),
 * no secrets, and uses textContent only. Failure leaves "unknown", never a guess. */
(function () {
  "use strict";
  function set(text, release) {
    var span = document.getElementById("szl-build-id");
    if (span) span.textContent = text;
    var meta = document.querySelector('meta[name="szl-release-id"]');
    if (meta) meta.setAttribute("content", release || "unknown");
  }
  function ok(v, re) { return typeof v === "string" && re.test(v) ? v : null; }
  fetch("/api/build", { cache: "no-store", credentials: "omit", headers: { Accept: "application/json" } })
    .then(function (r) { if (!r.ok) throw new Error("http " + r.status); return r.json(); })
    .then(function (b) {
      var release = ok(b && b.release_id, /^[0-9a-f]{12}$/);
      var commit = ok(b && b.git && b.git.commit, /^[0-9a-f]{40}$/);
      var status = ok(b && b.status, /^[A-Z_]{3,16}$/) || "UNKNOWN";
      set((release || "unknown") + " \u00b7 " + (commit ? commit.slice(0, 7) : "unknown") + " \u00b7 " + status, release);
    })
    .catch(function () { set("unknown (build endpoint unreachable)", null); });
})();
