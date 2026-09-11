"""Real ASGI message tests, not production browser evidence."""
from __future__ import annotations
import copy
import importlib.util
from pathlib import Path
import unittest

import szl_html_injection as MODULE

class HtmlTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, chunks, *, method='GET', path='/', status=200, headers=None, max_bytes=2000000, max_chunks=1024):
        headers = [(b'content-type',b'text/html')] if headers is None else headers
        events=[{'type':'http.response.start','status':status,'headers':headers}]
        events += [{'type':'http.response.body','body':b,'more_body':i<len(chunks)-1} for i,b in enumerate(chunks)]
        original=copy.deepcopy(events); received=[]
        async def app(scope,receive,send):
            for event in events:await send(event)
        async def send(event):received.append(event)
        async def receive():return {'type':'http.request','body':b'','more_body':False}
        middleware=MODULE.LandingInjectionMiddleware(app,max_bytes=max_bytes,max_chunks=max_chunks)
        await middleware({'type':'http','method':method,'path':path},receive,send)
        self.assertEqual(events,original)
        return received,original
    def body(self,events):return b''.join(e.get('body',b'') for e in events)
    async def test_injection_and_content_length(self):
        r,_=await self.run_case([b'<html><body>hello</body></html>'])
        self.assertIn(b'landing-honest-bind.js',self.body(r));self.assertEqual(int(dict(r[0]['headers'])[b'content-length']),len(self.body(r)))
    async def test_marker_split_across_chunks(self):
        r,_=await self.run_case([b'<body>x</bo',b'dy>']);self.assertIn(b'landing-honest-bind.js',self.body(r))
    async def test_exactly_once(self):
        r,o=await self.run_case([b'<body>landing-honest-bind.js</body>']);self.assertEqual(r,o)
    async def test_oversize_unknown_length_lossless(self):
        chunks=[b'<body>',b'x'*30,b'y'*30,b'</body>'];r,o=await self.run_case(chunks,max_bytes=10)
        self.assertEqual(r,o);self.assertEqual(self.body(r),b''.join(chunks))
    async def test_oversize_known_length_lossless(self):
        r,o=await self.run_case([b'x'*30],max_bytes=10,headers=[(b'content-type',b'text/html'),(b'content-length',b'30')]);self.assertEqual(r,o)
    async def test_chunk_limit_lossless(self):
        r,o=await self.run_case([b'<body>',b'',b'',b'</body>'],max_chunks=1);self.assertEqual(r,o)
    async def test_head_untouched(self):
        r,o=await self.run_case([b''],method='HEAD',headers=[(b'content-type',b'text/html'),(b'content-length',b'99')]);self.assertEqual(r,o)
    async def test_compressed_untouched(self):
        r,o=await self.run_case([b'COMPRESSED BYTES</body>'],headers=[(b'content-type',b'text/html'),(b'content-encoding',b'gzip')]);self.assertEqual(r,o)
    async def test_signed_or_digested_body_untouched(self):
        for header in [b'digest',b'content-digest',b'signature',b'signature-input',b'content-md5']:
            with self.subTest(header=header):
                r,o=await self.run_case([b'</body>'],headers=[(b'content-type',b'text/html'),(header,b'value')]);self.assertEqual(r,o)
    async def test_partial_untouched(self):
        r,o=await self.run_case([b'</body>'],status=206);self.assertEqual(r,o)
    async def test_content_range_untouched(self):
        r,o=await self.run_case([b'</body>'],headers=[(b'content-type',b'text/html'),(b'content-range',b'bytes 0-6/100')]);self.assertEqual(r,o)
    async def test_non_html_untouched(self):
        r,o=await self.run_case([b'</body>'],headers=[(b'content-type',b'application/json')]);self.assertEqual(r,o)
    async def test_non_root_untouched(self):
        r,o=await self.run_case([b'</body>'],path='/frontier-tooling');self.assertEqual(r,o)
    async def test_post_untouched(self):
        r,o=await self.run_case([b'</body>'],method='POST');self.assertEqual(r,o)
    async def test_absent_close_tag_untouched(self):
        r,o=await self.run_case([b'<body>abc']);self.assertEqual(r,o)
    async def test_stale_validators_removed_after_mutation(self):
        r,_=await self.run_case([b'</body>'],headers=[(b'content-type',b'text/html'),(b'etag',b'old'),(b'last-modified',b'old')])
        self.assertNotIn(b'etag',dict(r[0]['headers']));self.assertNotIn(b'last-modified',dict(r[0]['headers']))
    async def test_csp_preserved(self):
        h=(b'content-security-policy',b"default-src 'none'; script-src 'self'")
        r,_=await self.run_case([b'</body>'],headers=[(b'content-type',b'text/html'),h]);self.assertIn(h,r[0]['headers'])
    async def test_duplicate_content_type_passthrough(self):
        r,o=await self.run_case([b'</body>'],headers=[(b'content-type',b'text/html'),(b'content-type',b'application/json')]);self.assertEqual(r,o)
    async def test_invalid_length_passthrough(self):
        r,o=await self.run_case([b'</body>'],headers=[(b'content-type',b'text/html'),(b'content-length',b'invalid')]);self.assertEqual(r,o)
    async def test_header_names_case_insensitive(self):
        r,_=await self.run_case([b'</body>'],headers=[(b'Content-Type',b'text/html')]);self.assertIn(b'landing-honest-bind.js',self.body(r))
    async def test_exact_limit_is_not_truncated(self):
        raw=b'<body>x</body>';r,_=await self.run_case([raw],max_bytes=len(raw));self.assertTrue(self.body(r).endswith(b'</body>'))
    async def test_invalid_bounds(self):
        for limit in [0,-1,True,2000001]:
            with self.subTest(limit=limit),self.assertRaises(ValueError):MODULE.LandingInjectionMiddleware(None,max_bytes=limit)

if __name__=='__main__':unittest.main()
