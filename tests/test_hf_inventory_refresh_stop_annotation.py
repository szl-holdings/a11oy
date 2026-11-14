#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline contracts for HF inventory refresh stop visibility; no network, no gh call.

Runs under the prepare job's offline admission step (stdlib unittest only). The
workflow steps are executed in bash with a stub collector and a gh shell function,
so nothing here reaches GitHub or Hugging Face.
"""
import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DRIFT = ROOT / '.github/workflows/hf-ecosystem-drift.yml'
STOP_SCRIPT = ROOT / 'scripts/format_inventory_stop_annotation.py'
CHECK_SCRIPT = ROOT / 'scripts/format_hf_check_result.py'
REPORT_PATH = '"$RUNNER_TEMP/hf-inventory-source-review.json"'
ANNOTATE_RUN = f'python -I -B scripts/format_inventory_stop_annotation.py {REPORT_PATH}'
PREFIX = '::error title=HF inventory refresh stopped::'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S = load('format_inventory_stop_annotation', STOP_SCRIPT)
C = load('format_hf_check_result', CHECK_SCRIPT)
P = load('prepare_for_stop_annotation', ROOT / 'scripts/prepare_hf_inventory_refresh.py')


def step(workflow, name):
    start = workflow.index(f'      - name: {name}\n')
    end = re.search(r'\n(?=      - |      # |\n  \S|  \S)', workflow[start + 1:])
    return workflow[start:] if end is None else workflow[start:start + 1 + end.start()]


def run_block(text):
    lines = text.split('\n')
    first = lines.index('        run: |') + 1
    body = []
    for line in lines[first:]:
        if line.strip() and not line.startswith(' ' * 10):
            break
        body.append(line[10:])
    return '\n'.join(body).strip('\n') + '\n'


def bash(script, *, cwd, env):
    # GitHub runs `shell: bash` steps as `bash --noprofile --norc -eo pipefail {0}`.
    return subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', script],
                          cwd=cwd, env=env, capture_output=True, text=True, timeout=60, check=False)


def interpreter_bin(folder, *names, script=None):
    """A PATH entry whose python names run this interpreter, or a fixed failing script."""
    folder.mkdir()
    for name in names:
        target = folder / name
        if script is None:
            target.symlink_to(sys.executable)
        else:
            target.write_text(script, encoding='utf-8')
            target.chmod(0o755)
    return str(folder)


def report(**fields):
    value = {'schema': S.SCHEMA, 'state': 'NOT_CREATED', 'branchCreated': False}
    value.update(fields)
    return value


def governed_stop():
    return report(
        state='SOURCE_REVIEW_REQUIRED', preparationStep='GOVERNED_REVISION_PREFLIGHT',
        errorType='PreparationError',
        reason='governed Hugging Face revision changed; source review required, no routine refresh branch',
        governedRevisions={'state': 'SOURCE_REVIEW_REQUIRED', 'policySha256': 'e' * 64, 'changed': [
            {'repoType': 'model', 'id': 'EXAMPLE/governed-model', 'class': 'GOVERNED_EXACT',
             'policySource': 'fixture', 'change': 'REVISION_CHANGED', 'fields': ['sha', 'lastModified']},
            {'repoType': 'space', 'id': 'EXAMPLE/gated-space', 'class': 'GOVERNED_EXACT',
             'policySource': 'fixture', 'change': 'ADDED', 'fields': ['presence']}]})


class StopAnnotationFormatTests(unittest.TestCase):
    def render(self, value):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'report.json'
            if type(value) is bytes:
                path.write_bytes(value)
            else:
                path.write_text(value if type(value) is str else json.dumps(value), encoding='utf-8')
            return S.render(path)

    def test_designed_stop_names_state_step_reason_and_governed_changes(self):
        self.assertEqual(self.render(governed_stop()), PREFIX + (
            'SOURCE_REVIEW_REQUIRED at GOVERNED_REVISION_PREFLIGHT: governed Hugging Face revision changed; '
            'source review required, no routine refresh branch; governed changes: '
            'model:EXAMPLE/governed-model (sha,lastModified), space:EXAMPLE/gated-space (presence)'))

    def test_report_written_by_the_real_prepare_main_is_understood(self):
        def stop(source, run_id, artifact_id, digest, value):
            value.update(preparationStep='PUBLIC_ESTATE_PREFLIGHT')
            raise P.PreparationError('public estate classification or policy contract requires source review')
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'hf-inventory-source-review.json'
            argv = ['prepare', '--source', 'a' * 40, '--run-id', '7', '--artifact-id', '9',
                    '--artifact-digest', 'b' * 64, '--output', str(out)]
            with patch.object(P, 'prepare', stop), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
                self.assertEqual(P.main(), 1)
            self.assertEqual(S.render(out), PREFIX + 'NOT_CREATED at PUBLIC_ESTATE_PREFLIGHT: public estate '
                             'classification or policy contract requires source review')

    def test_untrusted_newlines_and_percent_cannot_start_another_command(self):
        line = self.render(report(state='X%Y', preparationStep='A\rB',
                                  reason='first\n::warning::forged\r\n::add-mask::x 100%'))
        self.assertEqual(line, PREFIX + 'X%25Y at A%0DB: first%0A::warning::forged%0D%0A::add-mask::x 100%25')
        self.assertNotIn('\n', line)
        self.assertNotIn('\r', line)
        self.assertEqual(line.count('::error '), 1)

    def test_properties_escape_colon_and_comma_too(self):
        self.assertEqual(S.escape_property('a:b,c%d\ne\rf'), 'a%3Ab%2Cc%25d%0Ae%0Df')
        self.assertEqual(S.escape_data('a:b,c%d\ne\rf'), 'a:b,c%25d%0Ae%0Df')

    def test_controls_format_characters_and_lone_surrogates_become_question_marks(self):
        line = self.render(report(reason='tab\there\x1b[31m‮evil sep\ud800end\x85'))
        self.assertEqual(line, PREFIX + 'NOT_CREATED at UNRECORDED: tab?here?[31m?evil?sep?end?')
        line.encode('utf-8')

    def test_length_is_capped_without_splitting_an_escape(self):
        for reason in ('x' * 5000, '%' * 5000, 'ab\n' * 2000):
            with self.subTest(reason=reason[:3]):
                line = self.render(report(reason=reason))
                self.assertLessEqual(len(line), S.MAX_LINE)
                self.assertTrue(line.endswith('...'))
                self.assertIsNone(re.search(r'%(?:[0-9A-F]?)\.\.\.\Z', line))
        many = report(governedRevisions={'changed': [
            {'repoType': 'model', 'id': f'EXAMPLE/m{i}', 'fields': ['sha']} for i in range(500)]})
        self.assertLessEqual(len(self.render(many)), S.MAX_LINE)

    def test_missing_or_malformed_fields_are_labelled_not_guessed(self):
        line = self.render(report(state=None, preparationStep=7, reason='',
                                  governedRevisions={'changed': ['bad', {'fields': 'sha'}, {'fields': [1]}]}))
        self.assertEqual(line, PREFIX + 'UNRECORDED at UNRECORDED: no reason recorded; governed changes: '
                         'UNRECORDED:UNRECORDED (UNRECORDED), UNRECORDED:UNRECORDED (UNRECORDED), '
                         'UNRECORDED:UNRECORDED (UNRECORDED)')
        self.assertNotIn('governed changes', self.render(report(governedRevisions={'changed': 'x'})))

    def test_missing_or_invalid_report_still_emits_one_annotation(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / 'absent.json'
            self.assertEqual(S.render(missing), PREFIX + f'stop report is missing: {missing}')
        cases = {'{': 'is not valid JSON', '{"schema": NaN}': 'is not valid JSON', '[]': 'is not a',
                 json.dumps({'schema': 'other', 'state': 'X'}): 'is not a', '[' * 100000: 'is not valid JSON',
                 b'{"schema": "\xff"}': 'is not valid JSON'}
        for raw, expected in cases.items():
            with self.subTest(raw=raw[:20]):
                line = self.render(raw)
                self.assertTrue(line.startswith(PREFIX + 'stop report '))
                self.assertIn(expected, line)
        with tempfile.TemporaryDirectory() as folder:
            big = Path(folder) / 'big.json'
            big.write_bytes(b' ' * (S.MAX_REPORT_BYTES + 1))
            self.assertIn('exceeds', S.render(big))

    def test_main_prints_exactly_one_line_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'report.json'
            path.write_text(json.dumps(governed_stop()), encoding='utf-8')
            result = subprocess.run([sys.executable, '-I', '-B', str(STOP_SCRIPT), str(path)],
                                    capture_output=True, timeout=60, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b'')
        lines = result.stdout.decode('utf-8').split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1], '')
        self.assertTrue(lines[0].startswith(PREFIX))


class CheckResultFormatTests(unittest.TestCase):
    audit = None

    @classmethod
    def setUpClass(cls):
        cls.audit = load('audit_for_check_result', ROOT / 'scripts/audit_huggingface_ecosystem.py')

    def collector_output(self, result, rows=None):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = self.audit.finish_check(result, 'Hugging Face ecosystem manifest is stale: x',
                                           output=Path('x'), report=None, rows=rows)
        return stream.getvalue(), code

    def test_every_real_collector_label_renders_as_one_code_span(self):
        rows = [{'change': 'CHANGED', 'repoType': 'model', 'id': 'EXAMPLE/`$(touch pwned)` @someone',
                 'class': 'SOURCE_TRACKED', 'fields': ['sha']}]
        for result in self.audit.CHECK_RESULTS:
            with self.subTest(result=result):
                text, code = self.collector_output(result, rows)
                self.assertEqual(C.render(text, str(code)),
                                 f'`{result} ({self.audit.RESULT_MEANING[result]})`')

    def test_label_must_agree_with_the_recorded_exit_code(self):
        text, _ = self.collector_output('DRIFT')
        current, _ = self.collector_output('CURRENT')
        for value, code in ((text, '0'), (current, '1'), (text, ''), (text, 'x'), (text, '1; rm')):
            with self.subTest(code=code):
                self.assertTrue(C.render(value, code).startswith('UNVERIFIED (labelled result '))

    def test_only_the_last_line_counts_and_odd_shapes_are_not_repaired(self):
        text, _ = self.collector_output('DRIFT')
        self.assertEqual(C.render(None, '1'), C.NOT_RECORDED)
        self.assertEqual(C.render('no result here\n', '1'), C.NOT_RECORDED)
        for forged in ('Hugging Face ecosystem check result: DRIFT (`$(id)` @org)',
                       'Hugging Face ecosystem check result: DRIFT (x) more',
                       'Hugging Face ecosystem check result: SOMETHING (x)'):
            with self.subTest(forged=forged):
                self.assertEqual(C.render(text + forged + '\n', '1'), C.UNEXPECTED)

    def test_cli_reads_a_bounded_tail_and_exits_zero_when_the_log_is_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'check.log'
            text, _ = self.collector_output('UNAVAILABLE')
            log.write_text('  row\n' * 50000 + text, encoding='utf-8')
            for path, expected in ((log, f"`UNAVAILABLE ({self.audit.RESULT_MEANING['UNAVAILABLE']})`"),
                                   (Path(folder) / 'absent.log', C.NOT_RECORDED)):
                result = subprocess.run([sys.executable, '-I', '-B', str(CHECK_SCRIPT), '--log', str(path),
                                         '--exit-code', '1'], capture_output=True, text=True, timeout=60,
                                        check=False)
                self.assertEqual((result.returncode, result.stdout), (0, expected + '\n'))


class StopVisibilityWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.drift = DRIFT.read_text(encoding='utf-8')
        self.prepare_job = self.drift.split('\n  prepare-source-review:\n', 1)[1]

    def test_annotation_step_is_failure_only_and_reads_only_the_report(self):
        annotate = step(self.drift, 'Annotate a stopped review-branch preparation')
        self.assertEqual(annotate, '      - name: Annotate a stopped review-branch preparation\n'
                                   "        if: failure() && steps.prepare.outcome == 'failure'\n"
                                   f'        run: {ANNOTATE_RUN}')
        prepare = step(self.drift, 'Create or fast-forward the rolling source review branch from this collector run')
        self.assertIn('        id: prepare\n', prepare)
        self.assertIn('--output "$RUNNER_TEMP/hf-inventory-source-review.json"', prepare)
        self.assertEqual(self.drift.count('id: prepare\n'), 1)
        names = re.findall(r'(?m)^      - (?:name: (.+)|uses: )', self.prepare_job)
        self.assertEqual([name for name in names if name][-3:], [
            'Create or fast-forward the rolling source review branch from this collector run',
            'Annotate a stopped review-branch preparation', 'Retain source proposal or stopping evidence'])

    def test_no_step_can_mask_the_stop_and_gates_are_unchanged(self):
        self.assertNotIn('continue-on-error', self.prepare_job)
        retain = step(self.drift, 'Retain source proposal or stopping evidence')
        self.assertIn('        if: always()\n', retain)
        self.assertIn('if-no-files-found: error', retain)
        self.assertEqual(self.drift.count('test "${STATE}" = "CURRENT"'), 1)
        enforce = step(self.drift, 'Enforce current public manifest')
        self.assertEqual(enforce, '      - name: Enforce current public manifest\n        if: always()\n'
                                  '        env:\n          STATE: ${{ steps.check.outputs.state }}\n'
                                  '        run: test "${STATE}" = "CURRENT"')
        self.assertIn('    permissions:\n      contents: write\n      actions: read\n      pull-requests: read\n'
                      '    steps:', self.prepare_job)
        self.assertIn('    permissions:\n      contents: read\n      issues: write\n', self.drift)
        self.assertNotIn('pull-requests: write', self.drift)
        self.assertNotIn('secrets.', self.drift)

    def test_annotation_step_runs_as_one_escaped_line_and_succeeds_on_any_report(self):
        hostile = report(state='SOURCE_REVIEW_REQUIRED', preparationStep='$(touch pwned)',
                         reason='`touch pwned`\n::warning::x %0A')
        for value in (hostile, None):
            with self.subTest(report=value is not None), tempfile.TemporaryDirectory() as folder:
                temp = Path(folder)
                if value is not None:
                    (temp / 'hf-inventory-source-review.json').write_text(json.dumps(value), encoding='utf-8')
                path = interpreter_bin(temp / 'bin', 'python')
                env = {'PATH': path + os.pathsep + os.environ.get('PATH', ''), 'RUNNER_TEMP': folder}
                result = bash(ANNOTATE_RUN, cwd=ROOT, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.count('\n'), 1)
                self.assertTrue(result.stdout.startswith(PREFIX))
                self.assertFalse((ROOT / 'pwned').exists() or (temp / 'pwned').exists())
                if value is not None:
                    self.assertIn('$(touch pwned): `touch pwned`%0A::warning::x %250A', result.stdout)

    def test_check_step_keeps_the_exit_code_state_mapping_through_tee(self):
        check = step(self.drift, 'Compare the tracked manifest with current public Hub evidence')
        self.assertIn('        shell: bash\n', check)
        self.assertNotIn('\n          code=$?\n', check)
        self.assertIn('            | tee "$RUNNER_TEMP/hf-ecosystem-check.log"\n'
                      '          code=${PIPESTATUS[0]}\n'
                      '          if [ "$code" -eq 0 ]; then\n'
                      "            state='CURRENT'\n"
                      '          else\n'
                      "            state='DRIFT_OR_UNAVAILABLE'\n"
                      '          fi\n', check)
        script = run_block(check)
        line = 'Hugging Face ecosystem check result: DRIFT (tracked manifest differs from current public Hub evidence)'
        for code, state in ((0, 'CURRENT'), (1, 'DRIFT_OR_UNAVAILABLE'), (7, 'DRIFT_OR_UNAVAILABLE')):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                temp = Path(folder)
                (temp / 'scripts').mkdir()
                (temp / 'scripts/audit_huggingface_ecosystem.py').write_text(
                    f'print({line!r})\nraise SystemExit({code})\n', encoding='utf-8')
                env = {'PATH': interpreter_bin(temp / 'bin', 'python3') + os.pathsep + os.environ.get('PATH', ''),
                       'RUNNER_TEMP': folder, 'GITHUB_OUTPUT': str(temp / 'output')}
                result = bash(script, cwd=temp, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((temp / 'output').read_text(encoding='utf-8'),
                                 f'state={state}\nexit_code={code}\n')
                self.assertEqual((temp / 'hf-ecosystem-check.log').read_text(encoding='utf-8'), line + '\n')

    def issue_body(self, log, exit_code, *, failing_python=False):
        sync = step(self.drift, 'Synchronize deterministic drift incident')
        self.assertIn('          CHECK_EXIT_CODE: ${{ steps.check.outputs.exit_code }}\n', sync)
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            if log is not None:
                (temp / 'hf-ecosystem-check.log').write_text(log, encoding='utf-8')
            # A shell function wins over every PATH entry, so the real gh is never reached.
            fake_gh = ('gh() {\n  printf "%s\\n" "$*" >> "$GH_CALLS"\n  previous=\n'
                       '  for argument in "$@"; do\n'
                       '    if [ "$previous" = --body-file ]; then cat "$argument" > "$ISSUE_BODY"; fi\n'
                       '    previous=$argument\n  done\n}\n')
            script = fake_gh + run_block(sync).replace('/tmp/hf-drift-issue.md', str(temp / 'draft.md'))
            bin_dir = (interpreter_bin(temp / 'bin', 'python3', script='#!/bin/sh\nexit 3\n') if failing_python
                       else interpreter_bin(temp / 'bin', 'python3'))
            env = {'PATH': bin_dir + os.pathsep + os.environ.get('PATH', ''), 'RUNNER_TEMP': folder,
                   'GH_CALLS': str(temp / 'calls'), 'ISSUE_BODY': str(temp / 'body.md'), 'GH_TOKEN': '',
                   'STATE': 'DRIFT_OR_UNAVAILABLE', 'CHECK_EXIT_CODE': exit_code,
                   'TITLE': '[HF-ECOSYSTEM-DRIFT] Public manifest is stale', 'GITHUB_REPOSITORY': 'owner/repo',
                   'GITHUB_SHA': 'a' * 40, 'GITHUB_SERVER_URL': 'https://github.example', 'GITHUB_RUN_ID': '42'}
            result = bash(script, cwd=ROOT, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('issue create', (temp / 'calls').read_text(encoding='utf-8'))
            self.assertFalse((temp / 'pwned').exists() or (ROOT / 'pwned').exists())
            return (temp / 'body.md').read_text(encoding='utf-8')

    def test_issue_body_carries_the_sanitized_labelled_check_result(self):
        rows = '  CHANGED model EXAMPLE/`$(touch pwned)` @someone [SOURCE_TRACKED] fields=sha\n'
        line = 'Hugging Face ecosystem check result: DRIFT (tracked manifest differs from current public Hub evidence)'
        body = self.issue_body('Hugging Face ecosystem manifest is stale: x\n' + rows + line + '\n', '1')
        self.assertIn('- State: DRIFT_OR_UNAVAILABLE\n- Check result: '
                      '`DRIFT (tracked manifest differs from current public Hub evidence)`\n- Candidate artifact:', body)
        self.assertNotIn('@someone', body)
        self.assertNotIn('$(', body)
        forged = self.issue_body(rows + 'Hugging Face ecosystem check result: DRIFT ($(touch pwned) @x)\n', '1')
        self.assertIn(f'- Check result: {C.UNEXPECTED}\n', forged)
        self.assertIn(f'- Check result: {C.NOT_RECORDED}\n', self.issue_body(None, ''))
        self.assertIn('- Check result: UNAVAILABLE (the check result could not be formatted)\n',
                      self.issue_body(line + '\n', '1', failing_python=True))


class FormatterSurfaceTests(unittest.TestCase):
    def test_formatters_import_only_inert_stdlib_modules(self):
        allowed = {'argparse', 'json', 'pathlib', 'sys', 'unicodedata', 're'}
        for path in (STOP_SCRIPT, CHECK_SCRIPT):
            with self.subTest(script=path.name):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                imported = {alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                            for alias in node.names}
                imported |= {node.module.split('.')[0] for node in ast.walk(tree)
                             if isinstance(node, ast.ImportFrom)}
                self.assertLessEqual(imported, allowed)
                calls = {node.func.attr for node in ast.walk(tree)
                         if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
                self.assertNotIn('write_text', calls)
                self.assertNotIn('write_bytes', calls)
                opens = re.findall(r"\.open\('([a-z]+)'\)", path.read_text(encoding='utf-8'))
                self.assertEqual(opens, ['rb'])


if __name__ == '__main__':
    unittest.main()
