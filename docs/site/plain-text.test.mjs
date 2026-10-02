// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import { strict as assert } from 'node:assert'
import { test } from 'node:test'
import { plainText } from './plain-text.mjs'

test('reads text nodes while excluding attributes, comments and executable subtrees', () => {
  for (const html of [
    '<p>Before</p><script>alert(1)</script><p>After</p>',
    '<p>Before</p><SCRIPT>alert(1)</SCRIPT><p>After</p>',
    '<p>Before</p><script>alert(1)</script ><p>After</p>',
    '<p>Before</p><style>.x{color:red}</style><p>After</p>',
    '<p>Before</p><STYLE>.x{color:red}</STYLE ><p>After</p>',
    '<p title="ignored > text" onclick="alert(1)">Before</p><!-- hidden --><p>After</p>',
  ]) assert.equal(plainText(html), 'Before After')
})

test('keeps encoded markup and Vue-like code as literal text for the textContent sink', () => {
  assert.equal(plainText('<code>&lt;script&gt;alert(1)&lt;/script&gt;</code>'), '<script>alert(1)</script>')
  assert.equal(plainText('<p>&#60;img&#x3e; &amp; &quot; &apos; &nbsp; &#x1f512;</p>'), '<img> & " \' 🔒')
  assert.equal(plainText('<code>{{ value }} &lt;div&gt;</code>'), '{{ value }} <div>')
  assert.equal(plainText('<math><mi>Λ</mi><mo>≤</mo><mn>1</mn></math>'), 'Λ ≤ 1')
})

test('fails closed on malformed HTML rather than indexing an unparsed fragment', () => {
  assert.throws(() => plainText('<p>text</wrong>'))
})
