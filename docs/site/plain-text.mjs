// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// Vue's locked HTML parser reads nodes; indexed strings remain text, never HTML.
import { parse } from '@vue/compiler-dom'

export function plainText(html) {
  const document = parse(html, { comments: false, whitespace: 'preserve', delimiters: ['\u0000', '\u0001'] })
  function text(node) {
    if (node.type === 2) return node.content
    if (node.type === 1 && /^(script|style)$/i.test(node.tag)) return ''
    return (node.children || []).map(text).join(' ')
  }
  return text(document).replace(/\s+/g, ' ').trim()
}
