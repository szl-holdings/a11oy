#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""One guarded fixture measurement; no production APIs or package downloads."""
import argparse
import ctypes
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from console_lighthouse_fixture import FixtureHandler, SOURCE_REVISION, CONSOLE_SHA256, ROOT


class BoundedFixtureHandler(FixtureHandler):
    def setup(self):
        self.request.settimeout(10)
        super().setup()


class FixtureServer(ThreadingHTTPServer):
    daemon_threads = True


def capacity():
    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in
            ('total', 'available', 'page_total', 'page_available', 'virtual_total', 'virtual_available', 'extended')]
    m = Memory()
    m.length = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise OSError('Capacity observation failed')
    return {'free_ram_bytes': m.available, 'free_disk_bytes': shutil.disk_usage(ROOT).free}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('mobile', 'desktop'), default='mobile')
    parser.add_argument('--view', choices=('fleet', 'readiness', 'estate'), default='fleet')
    args = parser.parse_args()
    admission = capacity()
    if admission['free_ram_bytes'] < 2 * 1024**3 or admission['free_disk_bytes'] < 2 * 1024**3:
        raise RuntimeError(f'Resource admission failed: {admission}')
    tool = (ROOT.parent / 'qa-tools/lighthouse-13.5.0').resolve()
    binary = Path.home() / 'AppData/Local/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-win64/chrome-headless-shell.exe'
    assert json.loads((tool / 'node_modules/lighthouse/package.json').read_text(encoding='utf-8'))['version'] == '13.5.0'
    assert hashlib.sha256((ROOT / 'pages/console.html').read_bytes()).hexdigest() == CONSOLE_SHA256
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    server, thread, origin = None, None, None
    observations = [admission]
    child = None
    metadata = {'source_revision': SOURCE_REVISION, 'console_sha256': CONSOLE_SHA256,
                'mode': args.mode, 'view': args.view, 'resources': observations,
                'source': 'LOCAL TEST FIXTURE; NOT PRODUCTION'}
    bound_files = [ROOT / 'scripts/measure_console_lighthouse.py', ROOT / 'scripts/console_lighthouse_measure.mjs',
                   ROOT / 'scripts/console_lighthouse_fixture.py', ROOT / 'scripts/test_console_mobile_integrity.py',
                   ROOT / 'pages/console.html', tool / 'package-lock.json', binary]
    for directory in ('static-vendor', 'console/assets', 'static/shared'):
        bound_files.extend(f for f in (ROOT / directory).rglob('*') if f.is_file())
    metadata['source_files'] = [{'path': str(f), 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()}
                                for f in sorted(set(bound_files))]
    metadata['qa_head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    guard_log = output / 'browser-request-guard.jsonl'
    guard_log.write_text('', encoding='utf-8')
    guard_errors = []

    def record_guard(row):
        with guard_log.open('a', encoding='utf-8') as log:
            log.write(json.dumps(row) + '\n')

    def guard_request(route):
        request = route.request
        parsed = urlsplit(request.url)
        allowed = f'{parsed.scheme}://{parsed.netloc}' == origin and request.method == 'GET'
        row = {'url': request.url, 'method': request.method, 'action': 'FORWARD_LOOPBACK' if allowed else 'ABORT'}
        try:
            if allowed:
                route.continue_()
            else:
                route.abort('blockedbyclient')
            row['acknowledged'] = True
        except Exception as error:
            row['acknowledged'] = False
            row['error'] = str(error)
            guard_errors.append(str(error))
        record_guard(row)

    def guard_websocket(route):
        row = {'url': route.url, 'action': 'ABORT_WEBSOCKET'}
        try:
            route.close(code=1008, reason='Local fixture has no WebSocket transport')
            row['acknowledged'] = True
        except Exception as error:
            row['acknowledged'] = False
            row['error'] = str(error)
            guard_errors.append(str(error))
        record_guard(row)
    try:
        server = FixtureServer(('127.0.0.1', 0), BoundedFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        metadata['origin'] = origin
        with tempfile.TemporaryDirectory(prefix='owned-profile-', dir=output, ignore_cleanup_errors=True) as profile:
            assert Path(profile).resolve().is_relative_to(output)
            metadata['owned_profile'] = profile
            with sync_playwright() as p:
                launch_capacity = capacity()
                observations.append(launch_capacity)
                if launch_capacity['free_ram_bytes'] < 2 * 1024**3 or launch_capacity['free_disk_bytes'] < 2 * 1024**3:
                    raise RuntimeError(f'Browser admission failed: {launch_capacity}')
                context = p.chromium.launch_persistent_context(profile, executable_path=str(binary), headless=True, service_workers='block',
                    args=['--disable-gpu', '--disable-background-networking', '--enable-automation', '--remote-debugging-port=0',
                          '--remote-debugging-address=127.0.0.1', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'])
                try:
                    context.route('**/*', guard_request)
                    context.route_web_socket('**/*', guard_websocket)
                    pump = context.pages[0]
                    port_file = Path(profile) / 'DevToolsActivePort'
                    for _ in range(50):
                        if port_file.is_file():
                            break
                        pump.wait_for_timeout(100)
                    debug_port = int(port_file.read_text(encoding='utf-8').splitlines()[0])
                    if not 0 < debug_port <= 65535:
                        raise RuntimeError('Invalid assigned debugger port')
                    with (output / 'node.log').open('w', encoding='utf-8') as log:
                        child = subprocess.Popen(['node', str(ROOT / 'scripts/console_lighthouse_measure.mjs'),
                            str(tool), str(debug_port), origin, str(output), args.mode, args.view, str(guard_log), profile], stdout=log, stderr=subprocess.STDOUT)
                        started = time.monotonic()
                        sampled = 0
                        while child.poll() is None:
                            elapsed = time.monotonic() - started
                            if elapsed - sampled >= 2:
                                current = capacity()
                                observations.append(current)
                                sampled = elapsed
                                if current['free_ram_bytes'] < 750 * 1024**2 or current['free_disk_bytes'] < 1024**3:
                                    raise RuntimeError(f'Resource stop: {current}')
                            if guard_errors:
                                raise RuntimeError(f'Browser request guard failed: {guard_errors}')
                            if elapsed > 300:
                                raise TimeoutError('Bounded pilot exceeded five minutes')
                            pump.wait_for_timeout(200)
                    metadata['exit_code'] = child.returncode
                finally:
                    try:
                        if child is not None and child.poll() is None:
                            child.terminate()
                            child.wait(timeout=10)
                    finally:
                        context.close()
        metadata['owned_profile_retained'] = Path(profile).exists()
    except Exception as error:
        metadata['error'] = str(error)
        metadata['exit_code'] = 1
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        if metadata.get('owned_profile'):
            metadata['owned_profile_retained'] = Path(metadata['owned_profile']).exists()
        metadata['completed_capacity'] = capacity()
        metadata['guard_errors'] = guard_errors
        (output / 'run-manifest.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps({key: metadata.get(key) for key in ('mode', 'view', 'exit_code', 'error', 'completed_capacity', 'owned_profile_retained')}))
    return metadata.get('exit_code', 1)


if __name__ == '__main__':
    raise SystemExit(main())
