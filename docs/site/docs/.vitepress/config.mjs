import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'
// Shiki is VitePress's own highlighter (locked in package-lock.json).
import { createCssVariablesTheme } from 'shiki'
import katexPlugin from '@vscode/markdown-it-katex'
const katex = katexPlugin.default || katexPlugin

// SZL Holdings unified documentation site.
// Tech: VitePress (Vite + Vue 3). Justification in /README.md.
// Math: KaTeX via @vscode/markdown-it-katex. Diagrams: Mermaid.
// Search: built-in local search (MiniSearch). No external service required.

const base = './'

export default withMermaid(defineConfig({
  base,
  // MPA mode: each page is fully static HTML with no client-side router.
  // Combined with a relative base, this lets the site render correctly
  // when served behind an unpredictable proxy sub-path (e.g. the pplx.app
  // preview). At the production root (docs.szlholdings.com) base '/' + SPA
  // can be restored. See README.
  mpa: true,
  lang: 'en-US',
  title: 'SZL Holdings Docs',
  description:
    'Unified documentation for SZL Holdings — math-grounded, Quechua-rooted governed-AI anatomy. Two shipping flagships (a11oy, killinchu) plus frontier roles, twelve organs, PURIQ agentic layer, Doctrine v11/v12.',
  cleanUrls: false,
  lastUpdated: true,
  ignoreDeadLinks: true,

  // Docs are the dark operator surface by default (SZL KANCHAY, founder
  // direction). VitePress light mode maps to the design system's light surface.
  appearance: 'dark',

  head: [
    // SZL KANCHAY 1.1.1 design system, vendored byte for byte at
    // docs/public/szl/ (served at ./szl/; fix-relative-paths.mjs depth-corrects
    // the href on nested pages). transformHtml below moves this link in front
    // of the theme stylesheet so the design system loads first. System font
    // stacks only: no webfont, no font CDN.
    ['link', { rel: 'stylesheet', href: './szl/szl-design-system.css' }],
    // MPA has no Vue hydration. Enhance its existing controls locally.
    ['script', { defer: '', src: './docs-ui.js' }],
    // szl-design-system.css keeps the dark operator surface on :root and the
    // light surface under [data-surface="light"]; VitePress toggles `.dark` on
    // <html>. Mirror it (initially and on every toggle): not dark -> light.
    ['script', { id: 'szl-surface-sync' },
      ';(() => { const r = document.documentElement; const s = () => { if (r.classList.contains(\'dark\')) r.removeAttribute(\'data-surface\'); else r.setAttribute(\'data-surface\', \'light\') }; s(); new MutationObserver(s).observe(r, { attributes: true, attributeFilter: [\'class\'] }) })()'],
    // Orbit favicons from the vendored logo suite (LOGO_USAGE.md).
    ['link', { rel: 'icon', type: 'image/svg+xml', href: './szl/logos/szl_favicon_square.svg' }],
    ['link', { rel: 'icon', type: 'image/png', sizes: '32x32', href: './szl/logos/szl_favicon_32.png' }],
    ['link', { rel: 'apple-touch-icon', sizes: '180x180', href: './szl/logos/szl_favicon_180.png' }],
    // Browser chrome tint. A meta value cannot reference a CSS variable: this
    // is --bg of the dark operator surface (--color-space-900).
    ['meta', { name: 'theme-color', content: '#030F29' }]
  ],

  // VitePress renders `head` entries after its own stylesheet. Move the design
  // system link in front of it so the tokens and base load first and the theme
  // (VitePress + custom.css) overrides them. Build-time only; `vitepress dev`
  // keeps the head order above.
  transformHtml(html) {
    const link = '<link rel="stylesheet" href="./szl/szl-design-system.css">'
    const at = html.indexOf('<link rel="preload stylesheet"')
    if (at < 0 || html.indexOf(link) < at) return html
    return html.slice(0, at) + link + '\n    ' + html.slice(at).replace(link, '')
  },

  markdown: {
    math: false,
    config: (md) => {
      // Native MathML keeps formulas without loading any webfonts.
      md.use(katex, { output: 'mathml' })
    },
    // Code blocks stay dark on both surfaces. Syntax colors are CSS variables
    // (--shiki-*) that custom.css maps onto the design system's code palette,
    // so no highlighter theme hex reaches the page.
    theme: createCssVariablesTheme({ name: 'szl-code' }),
    lineNumbers: false
  },

  themeConfig: {
    // The text title keeps the navbar neutral. The page's primary action or
    // active-nav marker is its one coral moment; a colored logo adds another.
    logo: false,
    siteTitle: 'SZL Holdings',

    nav: [
      { text: 'Home', link: '/' },
      { text: 'Quickstart', link: '/quickstart' },
      {
        text: 'Flagships',
        items: [
          { text: 'a11oy — execution fabric', link: '/flagships/a11oy' },
          { text: 'killinchu — drone intelligence', link: '/flagships/killinchu' },
          { text: 'Provenance Anchor', link: '/flagships/amaru' },
          { text: 'Operator — receipt orchestration', link: '/flagships/rosie' },
          { text: 'Policy — drift detector', link: '/flagships/sentra' }
        ]
      },
      {
        text: 'Anatomy',
        items: [
          { text: 'Architecture (7 organs)', link: '/architecture' },
          { text: 'Mesh — nervous system', link: '/mesh' },
          { text: 'Anatomy + Organs', link: '/anatomy/' },
          { text: 'PURIQ Doctrine', link: '/doctrine/puriq' },
          { text: 'Doctrine v11 + v12', link: '/doctrine/v11-v12' }
        ]
      },
      {
        text: 'Build',
        items: [
          { text: 'SDKs', link: '/sdks/' },
          { text: 'API Reference', link: '/api/' },
          { text: 'UDS — Unified Demo Surface (Coming Soon · Jun 16)', link: '/uds/' },
          { text: 'UDS — Deploy & Hand-off', link: '/uds' },
          { text: 'Cookbook', link: '/cookbook/' },
          { text: 'Use Cases', link: '/use-cases/' }
        ]
      },
      {
        text: 'Trust',
        items: [
          { text: 'Evidence', link: '/evidence/' },
          { text: 'Proof — Lean · Lake · DOIs', link: '/proof' },
          { text: 'Thesis Lineage — v1 → v22', link: '/lineage' },
          { text: 'Data Lake', link: '/lake' },
          { text: 'Changelog', link: '/changelog' },
          { text: 'Compliance & Security', link: '/compliance' },
          { text: 'Status', link: '/status' },
          { text: 'Brand Kit', link: '/brand' }
        ]
      },
      { text: 'About', link: '/about' }
    ],

    sidebar: {
      '/flagships/': [
        {
          text: 'Flagships',
          items: [
            { text: 'Overview', link: '/flagships/' },
            { text: 'a11oy', link: '/flagships/a11oy' },
            { text: 'killinchu', link: '/flagships/killinchu' },
            { text: 'Provenance Anchor', link: '/flagships/amaru' },
            { text: 'Operator', link: '/flagships/rosie' },
            { text: 'Policy', link: '/flagships/sentra' }
          ]
        }
      ],
      '/anatomy/': [
        {
          text: 'Anatomy',
          items: [
            { text: 'Anatomy + Organs', link: '/anatomy/' },
            { text: 'Mesh — nervous system', link: '/mesh' }
          ]
        },
        {
          text: 'The 12 Organs',
          collapsed: false,
          items: [
            { text: 'Amaru — cortex', link: '/anatomy/#amaru' },
            { text: 'Yuyay — heart', link: '/anatomy/#yuyay' },
            { text: 'Yawar — blood', link: '/anatomy/#yawar' },
            { text: 'Hukulla — immune', link: '/anatomy/#hukulla' },
            { text: 'Kallpa — wires', link: '/anatomy/#kallpa' },
            { text: 'Khipu — DAG', link: '/anatomy/#khipu' },
            { text: 'Lambda — spine', link: '/anatomy/#lambda' },
            { text: 'OTel-VSP — nerves', link: '/anatomy/#otel-vsp' },
            { text: 'Kanchay — brand', link: '/anatomy/#kanchay' },
            { text: 'Hatun — doctrine', link: '/anatomy/#hatun' },
            { text: 'Sumaq — designer', link: '/anatomy/#sumaq' },
            { text: 'Killinchu-bridge', link: '/anatomy/#killinchu-bridge' }
          ]
        }
      ],
      '/doctrine/': [
        {
          text: 'Doctrine',
          items: [
            { text: 'PURIQ Doctrine (v12)', link: '/doctrine/puriq' },
            { text: 'Doctrine v11 + v12 (LOCKED)', link: '/doctrine/v11-v12' }
          ]
        }
      ],
      '/sdks/': [
        {
          text: 'SDKs',
          items: [
            { text: 'Overview', link: '/sdks/' },
            { text: 'Python — szl-python', link: '/sdks/python' },
            { text: 'TypeScript — szl-ts', link: '/sdks/typescript' }
          ]
        }
      ],
      '/api/': [
        {
          text: 'API Reference',
          items: [
            { text: 'Overview', link: '/api/' },
            { text: 'a11oy API', link: '/api/a11oy' },
            { text: 'killinchu API', link: '/api/killinchu' }
          ]
        }
      ],
      '/cookbook/': [
        {
          text: 'Cookbook',
          items: [
            { text: 'Overview', link: '/cookbook/' },
            { text: 'anatomy-evolved-v1', link: '/cookbook/anatomy-evolved-v1' }
          ]
        }
      ],
      '/use-cases/': [
        {
          text: 'Use Cases',
          items: [
            { text: 'Overview', link: '/use-cases/' },
            { text: 'Warhacker mission packs', link: '/use-cases/warhacker' },
            { text: 'Greene demo flow', link: '/use-cases/greene-demo' },
            { text: 'Iron-Dome-but-the-brain', link: '/use-cases/iron-dome-brain' },
            { text: 'Sovereign AI for .gov', link: '/use-cases/sovereign-gov' }
          ]
        }
      ],
      '/evidence/': [
        {
          text: 'Evidence',
          items: [
            { text: 'Evidence Index', link: '/evidence/' }
          ]
        }
      ],
      '/uds/': [
        {
          text: 'UDS — Unified Demo Surface',
          items: [
            { text: 'Overview (Coming Soon · Jun 16)', link: '/uds/' }
          ]
        }
      ]
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/szl-holdings' }
    ],

    search: {
      provider: 'local',
      options: {
        detailedView: true
      }
    },

    outline: { level: [2, 3], label: 'On this page' },

    editLink: {
      pattern: 'https://github.com/szl-holdings/docs-site/edit/main/docs/:path',
      text: 'Edit this page on GitHub'
    },

    footer: {
      message:
        'Doctrine v11 LOCKED · 749/14/163 · kernel c7c0ba17 · Λ = Conjecture 1 · SLSA L1 honest. Math-grounded, Quechua-rooted, zero mysticism (PURIQ v12 agentic layer is additive).',
      copyright:
        'SZL Holdings · Authored by Yachay · ORCID 0009-0001-0110-4173'
    },

    lastUpdated: {
      text: 'Last updated',
      formatOptions: { dateStyle: 'medium' }
    }
  },

  mermaid: {
    theme: 'neutral',
    // Diagrams render inline, so the design system's body stack applies
    // (mermaid's own default face is not the brand's).
    fontFamily: 'var(--font-body)'
  }
}))
