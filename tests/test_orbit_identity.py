# SPDX-License-Identifier: Apache-2.0
"""Source-only orbital identity contracts; not live-runtime qualification."""

import hashlib
import json
import re
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER_HASH = "84a23d7b2a6dd198378ded91e52c545df2943fd33cbc4a67dd4184e94f4d94fb"
SOURCE_COMMIT = "2594f7f726cb14c6f123a948ad1c2d1d39ac9497"
BANNER_BLOB = "b3ddb97637d6d4a055ac3b449b68223366bdc742"


class HeadLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_head = False
        self.icons = []

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self.in_head = True
        values = dict(attrs)
        if self.in_head and tag == "link" and "icon" in values.get("rel", "").split():
            self.icons.append(values)

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False


class OrbitIdentityTests(unittest.TestCase):
    def test_projection_is_exact_admitted_source(self):
        record = json.loads((ROOT / "console/szl-orbit.source.json").read_text())
        data = (ROOT / "console/szl-orbit.svg").read_bytes()
        self.assertEqual(record["source_repository"], "szl-holdings/szl-brand")
        self.assertEqual(record["source_commit"], SOURCE_COMMIT)
        self.assertEqual(record["sha256"], MASTER_HASH)
        self.assertEqual(hashlib.sha256(data).hexdigest(), MASTER_HASH)
        self.assertEqual(record["live_deployment"], "NOT_ATTESTED")

    def test_native_favicon_url_is_byte_identical_alias(self):
        parser = HeadLinks()
        parser.feed((ROOT / "a11oy_landing.html").read_text(encoding="utf-8"))
        self.assertEqual(len(parser.icons), 1)
        self.assertEqual(parser.icons[0]["href"], "/social-preview-v5.svg")
        self.assertEqual(parser.icons[0]["type"], "image/svg+xml")
        self.assertEqual(
            (ROOT / "console/social-preview-v5.svg").read_bytes(),
            (ROOT / "console/szl-orbit.svg").read_bytes(),
        )
        self.assertIn("COPY console/ ./static/", (ROOT / "Dockerfile").read_text())

    def test_historical_banner_is_preserved_exactly(self):
        data = (ROOT / "console/social-preview-v5-banner.svg").read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        self.assertEqual(blob, BANNER_BLOB)
        root = ET.fromstring(data)
        self.assertEqual(root.attrib["viewBox"], "0 0 1280 640")
        self.assertIn("Evidence in. Receipts out.", data.decode())

    def test_icon_is_named_square_and_passive(self):
        data = (ROOT / "console/szl-orbit.svg").read_bytes()
        self.assertLess(len(data), 6000)
        self.assertNotIn(b"<!DOCTYPE", data)
        self.assertNotIn(b"<!ENTITY", data)
        root = ET.fromstring(data)
        self.assertEqual(root.attrib["viewBox"], "0 0 600 600")
        self.assertEqual(root.attrib["role"], "img")
        ids = [node.attrib["id"] for node in root.iter() if "id" in node.attrib]
        self.assertEqual(len(ids), len(set(ids)))
        for ref in root.attrib["aria-labelledby"].split():
            item = root.find(f".//*[@id='{ref}']")
            self.assertIsNotNone(item)
            self.assertTrue(item.text and item.text.strip())
        allowed = {"svg", "title", "desc", "defs", "linearGradient", "stop", "rect", "g", "ellipse", "path", "circle"}
        for node in root.iter():
            self.assertIn(node.tag.split("}")[-1], allowed)
            for key, value in node.attrib.items():
                self.assertFalse(key.lower().startswith("on"))
                self.assertFalse(key.lower().endswith("href"))
                if "url(" in value:
                    match = re.fullmatch(r"url\(#([A-Za-z][\w-]*)\)", value)
                    self.assertIsNotNone(match)
                    self.assertIn(match[1], ids)


if __name__ == "__main__":
    unittest.main()
