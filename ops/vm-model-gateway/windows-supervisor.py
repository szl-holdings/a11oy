#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Native Windows supervisor for the pinned proposal gateway and SSH transport."""
import hashlib, json, os, socket, subprocess, sys, time, ctypes
from ctypes import wintypes
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import build_opener, ProxyHandler
urlopen=build_opener(ProxyHandler({})).open
HOME = Path(__file__).resolve().parent
SOURCE = HOME / "source"
EXPECTED = {
 "ops/vm-model-gateway/gateway.py": "8b58af49453a5482586438d375e726bf0852adaeb5580147b0553c259878d080",
 "szl_dsse.py": "e095670051088929365f3eb4c76716122148d8f6b898db52f0e27867c221608c",
 "szl_content_address.py": "211b69d47fbbddf496fcfdedb0311e6fe6b67b67428100dd27ce7ce1f7247b10",
}
for rel, expected in EXPECTED.items():
 if hashlib.sha256((SOURCE / rel).read_bytes()).hexdigest() != expected:
  raise SystemExit("Pinned source mismatch")
if hashlib.sha256((HOME / "ssh-config").read_bytes()).hexdigest() != "bc209019d9db2cbc56f1efbf55dfbc3b1aded51defcc60b3e5a88660dd8b96e8":
 raise SystemExit("Pinned SSH configuration mismatch")
for port in (4000,19483):
 with socket.socket() as s:
  s.settimeout(1)
  if s.connect_ex(("127.0.0.1",port)) == 0:
   raise SystemExit("Existing listener preserved; startup refused")
key = (HOME / "gateway-bearer.key").read_text(encoding="ascii").strip()
pem = (HOME / "gateway-audit-p256.pem").read_text(encoding="ascii")
if len(key) < 32 or any(c.isspace() for c in key):
 raise SystemExit("Invalid private gateway credential")
os.environ["SZL_COSIGN_PRIVATE_PEM"] = pem
sys.path.insert(0,str(SOURCE))
import szl_dsse
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
ops = HOME / "operations"
ops.mkdir(exist_ok=True)
previous = None
def seal(phase, data):
 global previous
 payload = {"schema":"szl.native-vm-gateway-supervisor/v1",
  "at_utc":datetime.now(timezone.utc).isoformat(),"phase":phase,
  "previous_sha256":previous,"source_revision":"548ae61181d55ca72d9d7151c16e97b382277dae",
  "source_hashes":EXPECTED,"source_revision_evidence":"DECLARED",
  "measured_source_scope":"THREE_PINNED_COPIED_FILES","independent_witness":False,**data}
 env = szl_dsse.sign_payload(payload,"application/vnd.szl.gateway-supervisor+json")
 assert szl_dsse.verify_envelope(env)["verified"]
 env["honesty"]="REPORTED: local audit signature; no independent approval"
 env["key_trust"]="REPO_DECLARED"
 env.pop("verify_key_url",None)
 raw=json.dumps(env,sort_keys=True,separators=(",",":")).encode()
 with (ops/(stamp+"-"+phase+".dsse.json")).open("xb") as f:
  f.write(raw); f.flush(); os.fsync(f.fileno())
 previous=hashlib.sha256(raw).hexdigest()
seal("intent",{"effect":"Start pinned SSH tunnel and authenticated proposal gateway",
 "bind":"127.0.0.1:4000","upstream":"127.0.0.1:19483","production_acceptance":"BLOCKED"})
env={k:os.environ[k] for k in ("SystemRoot","WINDIR","PATH","TEMP","TMP","LOCALAPPDATA","APPDATA","USERPROFILE","USERNAME","USERDOMAIN","HOMEDRIVE","HOMEPATH","SystemDrive","COMSPEC","PATHEXT","ProgramData") if k in os.environ}
class BasicLimits(ctypes.Structure):
 _fields_=[("ProcessTime",ctypes.c_int64),("JobTime",ctypes.c_int64),("Flags",wintypes.DWORD),("MinWS",ctypes.c_size_t),("MaxWS",ctypes.c_size_t),("ActiveLimit",wintypes.DWORD),("Affinity",ctypes.c_size_t),("Priority",wintypes.DWORD),("Scheduling",wintypes.DWORD)]
class IoCounters(ctypes.Structure):
 _fields_=[(n,ctypes.c_uint64) for n in ("ReadOps","WriteOps","OtherOps","ReadBytes","WriteBytes","OtherBytes")]
class ExtendedLimits(ctypes.Structure):
 _fields_=[("Basic",BasicLimits),("Io",IoCounters),("ProcessMemory",ctypes.c_size_t),("JobMemory",ctypes.c_size_t),("PeakProcess",ctypes.c_size_t),("PeakJob",ctypes.c_size_t)]
kernel=ctypes.WinDLL("kernel32",use_last_error=True)
kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];kernel.SetInformationJobObject.restype=wintypes.BOOL
kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];kernel.AssignProcessToJobObject.restype=wintypes.BOOL
kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
job=kernel.CreateJobObjectW(None,None)
if not job: raise ctypes.WinError(ctypes.get_last_error())
limits=ExtendedLimits();limits.Basic.Flags=0x2000
if not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)):
 kernel.CloseHandle(job);raise ctypes.WinError(ctypes.get_last_error())

children=[]; handles=[]
def start(label,argv,child_env):
 out=(HOME/"logs"/(stamp+"-"+label+".stdout")).open("xb")
 err=(HOME/"logs"/(stamp+"-"+label+".stderr")).open("xb")
 handles.extend([out,err])
 p=subprocess.Popen(argv,cwd=str(HOME),env=child_env,stdin=subprocess.DEVNULL,
  stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
 children.append(p)
 if not kernel.AssignProcessToJobObject(job,wintypes.HANDLE(p._handle)):
  p.terminate();p.wait(timeout=5)
  raise ctypes.WinError(ctypes.get_last_error())
 return p
try:
 ssh=start("ssh",[r"C:\Program Files\OpenSSH\ssh.exe","-F",str(HOME/"ssh-config"),
  "-o","ClearAllForwardings=no","-o","ExitOnForwardFailure=yes","-N","-L",
  "127.0.0.1:19483:127.0.0.1:8080","szl-massed-qualification"],env)
 deadline=time.monotonic()+15
 while True:
  if ssh.poll() is not None: raise RuntimeError("SSH exited before readiness: "+str(ssh.returncode))
  try:
   with urlopen("http://127.0.0.1:19483/health",timeout=1) as r:
    if r.status==200: break
  except Exception: pass
  if time.monotonic()>deadline: raise RuntimeError("SSH health deadline")
  time.sleep(.5)
 gateway_env={**env,"SZL_LITELLM_KEY":key,"SZL_COSIGN_PRIVATE_PEM":pem,
  "SZL_VM_GATEWAY_RECEIPTS_DIR":str(HOME/"receipts"),"PYTHONNOUSERSITE":"1","PYTHONDONTWRITEBYTECODE":"1"}
 gateway=start("gateway",[sys.executable,"-I","-B","-u",str(SOURCE/"ops/vm-model-gateway/gateway.py")],gateway_env)
 deadline=time.monotonic()+10
 while True:
  if gateway.poll() is not None: raise RuntimeError("Gateway exited before readiness")
  try:
   with urlopen("http://127.0.0.1:4000/health",timeout=1) as r:
    health=json.load(r)
    if r.status==200 and health.get("instance_id"): break
  except Exception: pass
  if time.monotonic()>deadline: raise RuntimeError("Gateway health deadline")
  time.sleep(.5)
 state={"at_utc":datetime.now(timezone.utc).isoformat(),"ssh_pid":ssh.pid,
  "gateway_pid":gateway.pid,"instance_id":health["instance_id"],
  "source_revision":"548ae61181d55ca72d9d7151c16e97b382277dae",
  "evidence_class":"MEASURED","production_acceptance":"BLOCKED",
  "liveness_requires_fresh_probe":True,"state":"STARTED"}
 (HOME/"current-processes.json").write_text(json.dumps(state,indent=2))
 seal("started",state)
 while all(p.poll() is None for p in children): time.sleep(1)
 raise RuntimeError("Owned child exited; scheduler may retry startup, never inference")
except Exception as exc:
 seal("failure",{"error_type":type(exc).__name__,"message":str(exc)})
 raise
finally:
 for p in reversed(children):
  if p.poll() is None:
   p.terminate()
   try: p.wait(timeout=5)
   except subprocess.TimeoutExpired: p.kill();p.wait(timeout=5)
 kernel.CloseHandle(job)
 (HOME/"current-processes.json").write_text(json.dumps({"at_utc":datetime.now(timezone.utc).isoformat(),"state":"STOPPED","liveness_requires_fresh_probe":True}))
 for f in handles:f.close()
