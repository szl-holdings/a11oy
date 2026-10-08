// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import postcss from "postcss";
import { twMerge } from "tailwind-merge";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
type Lock = { packages: Record<string, { version?: string }> };
const removedAncestry = new Set(["braces", "micromatch", "fast-glob"]);

function legacyDependencies(lock: Lock): string[] {
  return Object.entries(lock.packages).filter(([name, entry]) => {
    const packageName = name.split("/node_modules/").at(-1)?.replace(/^node_modules\//, "");
    return removedAncestry.has(packageName ?? "") ||
      (packageName === "tailwindcss" && !entry.version?.startsWith("4.")) ||
      (packageName === "chokidar" && Number(entry.version?.split(".")[0]) < 4);
  }).map(([name]) => name);
}

function shippedCss() {
  const staticRoot = path.resolve(root, "../../civilian_observatory/static");
  const html = fs.readFileSync(path.join(staticRoot, "index.html"), "utf8");
  const cssPath = html.match(/href="\.\/assets\/(index-[^"]+\.css)"/);
  assert.ok(cssPath, "shipped index must reference its exact application CSS");
  return postcss.parse(fs.readFileSync(path.join(staticRoot, "assets", cssPath[1]), "utf8"));
}

function hasDeclaration(css: postcss.Root, selector: string, property: string, value: string) {
  let found = false;
  css.walkRules(rule => {
    if (!rule.selectors.includes(selector)) return;
    if (rule.nodes.some(node => node.type === "decl" && node.prop === property && node.value === value)) found = true;
  });
  return found;
}

function hasForcedColorOutline(css: postcss.Root, selector: string) {
  let found = false;
  css.walkRules(rule => {
    if (!rule.selectors.includes(selector)) return;
    const declarations = new Map(rule.nodes.filter(node => node.type === "decl")
      .map(node => [node.prop, node.value]));
    if (declarations.get("outline") !== "2px solid #0000" || declarations.get("outline-offset") !== "2px") return;
    for (let parent: postcss.Root | postcss.Document | postcss.AtRule | postcss.Rule | undefined = rule.parent;
        parent; parent = parent.parent) {
      if (parent.type === "atrule" && parent.name === "media" &&
          parent.params.replace(/\s/g, "") === "(forced-colors:active)") found = true;
    }
  });
  return found;
}

test("the complete interface lock graph excludes the removed Tailwind v3 ancestry", () => {
  const lock = JSON.parse(fs.readFileSync(path.join(root, "package-lock.json"), "utf8")) as Lock;
  assert.deepEqual(legacyDependencies(lock), []);
  assert.equal(lock.packages["node_modules/tailwindcss"].version, "4.3.3");
  assert.equal(lock.packages["node_modules/@tailwindcss/vite"].version, "4.3.3");
  assert.equal(lock.packages["node_modules/tailwind-merge"].version, "3.7.0");
});

test("nested legacy dependencies fail the graph guard, even alongside Tailwind v4", () => {
  assert.deepEqual(legacyDependencies({ packages: {
    "node_modules/tailwindcss": { version: "4.3.3" },
    "node_modules/example/node_modules/tailwindcss": { version: "3.4.19" },
    "node_modules/example/node_modules/braces": { version: "3.0.3" },
    "node_modules/chokidar": { version: "3.6.0" },
  } }), ["node_modules/example/node_modules/tailwindcss", "node_modules/example/node_modules/braces", "node_modules/chokidar"]);
});

test("v4 class merging respects forced-color outlines and CSS variable utility types", () => {
  assert.equal(twMerge("outline-none outline-hidden"), "outline-hidden");
  assert.equal(twMerge("origin-center origin-(--radix-tooltip-content-transform-origin)"), "origin-(--radix-tooltip-content-transform-origin)");
  assert.equal(twMerge("bg-background bg-primary text-foreground text-primary-foreground"), "bg-primary text-primary-foreground");
});

test("the actual focus controls and tooltip retain the v4 compatibility utilities", () => {
  for (const [file, utility] of [
    ["button.tsx", "focus-visible:outline-hidden"],
    ["input.tsx", "focus-visible:outline-hidden"],
    ["textarea.tsx", "focus-visible:outline-hidden"],
    ["dialog.tsx", "focus:outline-hidden"],
    ["sheet.tsx", "focus:outline-hidden"],
    ["toast.tsx", "focus:outline-hidden"],
  ]) {
    const source = fs.readFileSync(path.join(root, "client/src/components/ui", file), "utf8");
    assert.ok(source.includes(utility), `${file} must retain ${utility}`);
    assert.equal(source.includes("outline-none"), false, `${file} must not remove forced-color focus outlines`);
  }
  const tooltip = fs.readFileSync(path.join(root, "client/src/components/ui/tooltip.tsx"), "utf8");
  assert.ok(tooltip.includes("origin-(--radix-tooltip-content-transform-origin)"));
  assert.equal(tooltip.includes("origin-[--radix-tooltip-content-transform-origin]"), false);
});

test("shipped CSS emits layout, theme, motion, focus and variable utilities", () => {
  const css = shippedCss();
  for (const [selector, property, value] of [
    [".h-svh", "height", "100svh"],
    [".bg-background", "background-color", "hsl(var(--background) / 1)"],
    [".text-foreground", "color", "hsl(var(--foreground) / 1)"],
    [".outline-hidden", "outline", "2px solid #0000"],
    [".focus-visible\\:outline-hidden:focus-visible", "outline", "2px solid #0000"],
    [".origin-\\(--radix-tooltip-content-transform-origin\\)", "transform-origin", "var(--radix-tooltip-content-transform-origin)"],
    [".animate-in", "animation-name", "enter"],
  ]) assert.ok(hasDeclaration(css, selector, property, value), `missing ${selector}: ${property}: ${value}`);
  for (const selector of [".outline-hidden", ".focus\\:outline-hidden:focus", ".focus-visible\\:outline-hidden:focus-visible"]) {
    assert.ok(hasForcedColorOutline(css, selector), `${selector} must retain its forced-color outline and offset`);
  }
  assert.ok(css.toString().includes("prefers-reduced-motion:reduce"), "reduced-motion policy must survive the build");
  assert.ok(css.toString().includes("@media"), "responsive utilities must be emitted");
  assert.equal(css.toString().includes("@tailwind"), false);
  assert.equal(css.toString().includes("@apply"), false);
});

test("a missing utility cannot pass the emitted-CSS assertion", () => {
  const broken = postcss.parse(".outline-hidden { outline-style: none }");
  assert.equal(hasDeclaration(broken, ".outline-hidden", "outline", "2px solid #0000"), false);
});

test("lookalike classes, sibling classes, and nested child declarations cannot satisfy a utility", () => {
  for (const source of [
    ".h-svh-other { height: 100svh }",
    ".h-svh-other, .sibling { height: 100svh }",
    ".h-svh .child { height: 100svh }",
    ".h-svh { .child { height: 100svh } }",
  ]) assert.equal(hasDeclaration(postcss.parse(source), ".h-svh", "height", "100svh"), false);
  assert.equal(hasDeclaration(postcss.parse(".sibling, .h-svh { height: 100svh }"), ".h-svh", "height", "100svh"), true);
});

test("unrelated media, selectors, offsets, and child declarations cannot satisfy forced-color focus", () => {
  const selector = ".focus-visible\\:outline-hidden:focus-visible";
  const declaration = "outline: 2px solid #0000; outline-offset: 2px";
  for (const source of [
    `${selector} { ${declaration} }`,
    `@media (prefers-reduced-motion: reduce) { ${selector} { ${declaration} } }`,
    `@media (forced-colors: active) { .other { ${declaration} } }`,
    `@media (forced-colors: active) { ${selector} { outline: 2px solid #0000; outline-offset: 0 } }`,
    `@media (forced-colors: active) { ${selector} { .child { ${declaration} } } }`,
  ]) assert.equal(hasForcedColorOutline(postcss.parse(source), selector), false);
  assert.equal(hasForcedColorOutline(postcss.parse(`@media (forced-colors: active) { ${selector} { ${declaration} } }`), selector), true);
});
