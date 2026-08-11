#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PATTERNS = {
    "github_pat": re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "hf_token": re.compile(r"hf_[A-Za-z0-9]{30,}"),
    "generic_secret_assignment": re.compile(r"(?i)(api[_-]?key|secret|access[_-]?token)\s*[=:]\s*['\"][A-Za-z0-9_\-]{24,}['\"]"),
}
SKIP_DIRS={".git",".venv","build","dist","dist-repeat","__pycache__",".pytest_cache","run"}
TEXT_SUFFIXES={".py",".md",".json",".yml",".yaml",".toml",".txt",".html",".js",".css",".rego",".in"}

def scan(root: Path):
    findings=[]
    for path in sorted(root.rglob('*')):
        if not path.is_file() or set(path.relative_to(root).parts)&SKIP_DIRS or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:text=path.read_text(encoding='utf-8')
        except UnicodeDecodeError:continue
        for name,pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line=text.count('\n',0,match.start())+1
                findings.append({"path":path.relative_to(root).as_posix(),"line":line,"pattern":name})
    return findings

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--output',type=Path);args=ap.parse_args()
    findings=scan(args.root.resolve())
    report={"schema":"szl.static-secret-scan/v1","status":"PASS" if not findings else "FAIL","finding_count":len(findings),"findings":findings}
    text=json.dumps(report,sort_keys=True,indent=2)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8')
    print(text,end='');raise SystemExit(0 if not findings else 1)
if __name__=='__main__':main()
