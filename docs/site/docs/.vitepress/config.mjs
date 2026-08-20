import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'
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

  head: [
    ['link', { rel: 'preconnect', href: 'https://fonts.googleapis.com' }],
    ['link', { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' }],
    ['link', {
      rel: 'stylesheet',
      href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap'
    }],
    ['link', {
      rel: 'stylesheet',
      href: 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css'
    }],
    ['meta', { name: 'theme-color', content: '#0B1F3A' }]
  ],

  markdown: {
    math: false,
    config: (md) => {
      md.use(katex)
    },
    theme: { light: 'github-light', dark: 'github-dark' },
    lineNumbers: false
  },

  themeConfig: {
    // Navbar logo: committed static szl-mark.svg at /img/szl-mark.svg.
    // (Previously pointed at szl-avatar-animated.gif, which was never
    // committed to the repo and rendered broken — repointed to the
    // existing asset.)
    logo: '/img/szl-mark.svg',
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
          { text: '3D Showcases', link: '/anatomy/3d-showcases' },
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
            { text: 'Mesh — nervous system', link: '/mesh' },
            { text: '3D Showcases', link: '/anatomy/3d-showcases' }
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
    theme: 'neutral'
  }
}))
