// Post-build: make the VitePress static bundle fully relocatable so it renders
// correctly behind an unpredictable proxy sub-path (the pplx.app preview)
// without depending on a fixed `base`.
//
// Two transforms:
//   1. Depth-correct relative refs. VitePress with base:'./' emits `./assets`,
//      `./img`, and `./page.html` references that are only correct for
//      root-level pages. For nested pages (e.g. flagships/a11oy.html) the `./`
//      must become `../` × depth.
//   2. Explicit directory-index links. The preview proxy does NOT auto-serve
//      index.html for a trailing-slash URL, so rewrite relative links ending
//      in `/` (optionally + #anchor) to point at `index.html` explicitly.
//
// Idempotent and deterministic. Runs automatically after `vitepress build`
// (wired into the docs:build script).

import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'

const DIST = new URL('./docs/.vitepress/dist/', import.meta.url).pathname

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    const s = statSync(p)
    if (s.isDirectory()) walk(p, out)
    else if (name.endsWith('.html')) out.push(p)
  }
  return out
}

// Append index.html to relative directory-index links (href ending in `/`,
// optionally followed by an #anchor). Leaves http(s)://, //, #-only,
// mailto:, and tel: refs untouched.
function fixDirIndex(html) {
  return html.replace(/href="([^"]+)"/g, (m, url) => {
    if (/^(https?:|\/\/|#|mailto:|tel:)/.test(url)) return m
    const mm = url.match(/^([^#]*\/)(#.*)?$/)
    if (!mm) return m
    return `href="${mm[1]}index.html${mm[2] || ''}"`
  })
}

const files = walk(DIST)
let changed = 0

for (const file of files) {
  const rel = relative(DIST, file)
  const depth = rel.split(sep).length - 1
  let html = readFileSync(file, 'utf8')
  const before = html

  // 1) depth-correct `./` references (only needed for nested pages)
  if (depth > 0) {
    const prefix = '../'.repeat(depth)
    html = html.replace(/((?:href|src)=")\.\/(?!\/)/g, `$1${prefix}`)
    html = html.replace(/(["'(])\.\/assets\//g, `$1${prefix}assets/`)
  }

  // 2) explicit directory-index links (all pages, including root)
  html = fixDirIndex(html)

  if (html !== before) {
    writeFileSync(file, html)
    changed++
  }
}

console.log(`fix-relative-paths: rewrote ${changed} HTML file(s) of ${files.length} total.`)
