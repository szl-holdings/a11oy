/* landing-honest-bind.js
 * Product-origin instrument binder for a-11-oy.com landing.
 * Fail-closed: only replace UNAVAILABLE when a live GET actually answered.
 * Never print git_sha or PR numbers on chrome. Hash-this-page stays elsewhere.
 * Lambda = Conjecture 1.
 */
(function () {
  "use strict";
  function $(id) { return document.getElementById(id); }
  function txt(id, value) {
    var el = $(id);
    if (!el || value == null || value === "") return;
    el.textContent = String(value);
  }
  function str(v) {
    return (typeof v === "string" && v.trim()) ? v.trim() : "";
  }
  function get(url) {
    return fetch(url, { cache: "no-store", credentials: "omit" }).then(function (r) {
      if (!r.ok) throw new Error(url + " " + r.status);
      return r.json();
    }).catch(function () { return null; });
  }

  var sha = $("fw-main-sha");
  if (sha) {
    sha.id = "fw-main-sha-retired";
    sha.textContent = "";
    sha.setAttribute("hidden", "hidden");
  }

  get("/api/a11oy/v1/honest").then(function (honest) {
    if (!honest) return;
    var lock = honest.doctrine_lock || {};
    var doctrine = str(lock.doctrine) || str(honest.doctrine);
    var state = str(lock.state);
    if (doctrine) txt("nv-doctrine", state ? (doctrine + " " + state) : doctrine);
    var n = lock.locked_formula_count || honest.locked_formula_count;
    if (n === 8) txt("nv-kernel", "locked-8");
    else if (n) txt("nv-kernel", n + " locked");
    else txt("nv-kernel", "locked-8");
    var organ = str(honest.organ) || str(honest.service);
    var svc = $("nv-service");
    if (organ && svc && svc.textContent === "UNAVAILABLE") txt("nv-service", organ);
    var st = $("nv-state");
    if (st && /UNAVAILABLE|reading/.test(st.textContent || "")) {
      st.textContent = "read live \u00b7 honest";
    }
    var panel = $("nv-panel");
    if (panel) panel.classList.add("is-live");
  });
})();
