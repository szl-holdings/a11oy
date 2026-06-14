// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/energy.js — Energy · Harvest surface (holographic 3D energy-ops showcase).
//
// This surface delegates to the SHARED energy showcase module so the exact same
// 16-19 live 3D graphs render on all three surfaces (a11oy energy page, this
// /holographic shell tab, and the HF Space). Nothing here fabricates a value:
// every graph is wired by buildShowcase() to a real a11oy energy endpoint via
// ctx.live.poll and carries its doctrine honesty chip (MEASURED/MODELED/...).
//
// CONTRACT — { id, title, endpoints[], mount(ctx), unmount() }.
// ctx (provided by the /holographic shell via szl3d): stage, container, live,
// label, THREE, szl3d. mount() builds the showcase; unmount() disposes it.

import { buildShowcase, SHOWCASE_GRAPHS, SHOWCASE_ENDPOINTS } from "/static/3d/energy_showcase/showcase.js";

const ID = "energy";
const TITLE = "Energy · Holographic Ops";
const ENDPOINTS = Array.from(new Set(SHOWCASE_GRAPHS.map((g) => g.endpoint).filter(Boolean)));

let _showcase = null;

function mount(ctx) {
  _showcase = buildShowcase(ctx);
  return { id: ID, started: true, graphs: _showcase.count, endpoints: _showcase.endpoints };
}

function unmount() {
  try { if (_showcase) _showcase.dispose(); } catch (_) {}
  _showcase = null;
}

export default { id: ID, title: TITLE, endpoints: ENDPOINTS, mount, unmount };
export { SHOWCASE_GRAPHS, SHOWCASE_ENDPOINTS };
