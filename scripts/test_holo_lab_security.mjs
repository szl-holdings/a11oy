import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(
  path.join(here, '..', 'static', '3d', 'holo-lab.html'),
  'utf8',
);

const start = source.indexOf('function escAttr(s)');
const end = source.indexOf('function kchip', start);

assert.ok(start >= 0, 'holo-lab.html must define escAttr');
assert.ok(end > start, 'escAttr must appear before kchip');

const definition = source.slice(start, end);
const escAttr = new Function(`${definition}; return escAttr;`)();

assert.equal(
  escAttr(`node&<>"'`),
  'node&amp;&lt;&gt;&quot;&#39;',
  'attribute escaping must cover ampersands, brackets, and both quote types',
);
assert.equal(
  escAttr('" onmouseover="alert(1)'),
  '&quot; onmouseover=&quot;alert(1)',
  'an injected quote must not terminate data-id',
);
assert.ok(
  source.includes(`data-id="\${escAttr(n.id)}"`),
  'untrusted node identifiers must use the attribute-context escaper',
);
assert.ok(
  !source.includes('data-id="${esc(n.id)}"'),
  'the text-only escaper must not be used in data-id',
);

console.log('holo-lab attribute-escape regression: PASS');
