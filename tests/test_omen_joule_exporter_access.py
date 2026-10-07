"""The local GPU exporter denies ordinary network clients before reading telemetry."""

import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock


_MODULE_PATH = Path(__file__).resolve().parents[1] / "box-scripts" / "omen_joule_exporter.py"
_SPEC = importlib.util.spec_from_file_location("omen_joule_exporter_access_test", _MODULE_PATH)
_EXPORTER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_EXPORTER)


class _Request(_EXPORTER.Handler):
    def __init__(self, address):
        self.client_address = (address, 12345)
        self.code = None
        self.wfile = io.BytesIO()

    def send_response(self, code):
        self.code = code

    def send_error(self, code, *args):
        self.code = code

    def send_header(self, *args):
        pass

    def end_headers(self):
        pass


class RequestSourceGuardTests(unittest.TestCase):
    def test_loopback_and_tailnet_sources_keep_the_meter_usable(self):
        for address in ("127.0.0.1", "::1", "100.64.0.1", "100.127.255.254", "fd7a:115c:a1e0::1"):
            with self.subTest(address=address):
                request = _Request(address)
                with mock.patch.object(_EXPORTER, "_meter_json", return_value={"joules": 1}):
                    request.do_GET()
                self.assertEqual(request.code, 200)
                self.assertEqual(json.loads(request.wfile.getvalue()), {"joules": 1})

    def test_other_sources_are_rejected_before_telemetry_read(self):
        for address in ("192.168.1.163", "8.8.8.8", "100.128.0.1", "fe80::1", "invalid"):
            with self.subTest(address=address):
                request = _Request(address)
                with mock.patch.object(_EXPORTER, "_meter_json", side_effect=AssertionError("telemetry read")):
                    request.do_GET()
                self.assertEqual(request.code, 403)
                self.assertEqual(request.wfile.getvalue(), b"")


if __name__ == "__main__":
    unittest.main()
