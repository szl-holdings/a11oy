#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Native Windows supervisor for the pinned proposal gateway and SSH transport."""
import hashlib, json, os, subprocess, sys, time, ctypes
from ctypes import wintypes
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import build_opener, ProxyHandler
urlopen=build_opener(ProxyHandler({})).open
HOME = Path(__file__).resolve().parent
SOURCE = HOME / "source"
EXPECTED = {
 "ops/vm-model-gateway/gateway.py": "d0eda48d20813ad8a91f99168b4a9bccadf10cb34dddf77d93b64fe829af34e9",
 "ops/vm-model-gateway/runtime_config.py": "370902b7c22fdb66f2bfed68b1991ccad82d173b1ebc553d53d020ee6bd389f3",
 "szl_dsse.py": "dbe0188605d77610dee97f5b6efc069166a2a15fe46cf4f89881d4f5fa209d2f",
 "szl_content_address.py": "211b69d47fbbddf496fcfdedb0311e6fe6b67b67428100dd27ce7ce1f7247b10",
}
# The release identity is the exact, measured four-file manifest digest,
# not an invented Git commit SHA; source commit is verified at installation.
SOURCE_REVISION = "four-file-sha256:" + hashlib.sha256(
 json.dumps(EXPECTED, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
for rel, expected in EXPECTED.items():
 if hashlib.sha256((SOURCE / rel).read_bytes()).hexdigest() != expected:
  raise SystemExit("Pinned source mismatch")
if hashlib.sha256((HOME / "ssh-config").read_bytes()).hexdigest() != "8ec67f450d6cb9bb46b358c9c26b0c19cc50a75b90aee924fd8201616b9ff4b5":
 raise SystemExit("Pinned SSH configuration mismatch")
sys.path.insert(0,str(SOURCE / "ops" / "vm-model-gateway"))
from runtime_config import LocalTransport
transport = LocalTransport.from_file(HOME / "transport-config.json")
transport.require_free_ports()
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
  "previous_sha256":previous,"source_revision":SOURCE_REVISION,
  "source_hashes":EXPECTED,"source_revision_evidence":"MEASURED_PINNED_FOUR_FILE_MANIFEST",
  "source_revision_kind":"FOUR_FILE_SHA256",
  "measured_source_scope":"FOUR_PINNED_COPIED_FILES","independent_witness":False,**data}
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
 "bind":transport.gateway_bind,"upstream":transport.upstream,"production_acceptance":"BLOCKED"})
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
  transport.ssh_forward,"szl-massed-qualification"],env)
 deadline=time.monotonic()+15
 while True:
  if ssh.poll() is not None: raise RuntimeError("SSH exited before readiness: "+str(ssh.returncode))
  try:
   with urlopen(transport.health_url,timeout=1) as r:
    if r.status==200: break
  except Exception: pass
  if time.monotonic()>deadline: raise RuntimeError("SSH health deadline")
  time.sleep(.5)
 gateway_env={**env,**transport.gateway_environment,"SZL_LITELLM_KEY":key,"SZL_COSIGN_PRIVATE_PEM":pem,
  "SZL_VM_GATEWAY_RECEIPTS_DIR":str(HOME/"receipts"),"PYTHONNOUSERSITE":"1","PYTHONDONTWRITEBYTECODE":"1"}
 gateway=start("gateway",[sys.executable,"-I","-B","-u",str(SOURCE/"ops/vm-model-gateway/gateway.py")],gateway_env)
 deadline=time.monotonic()+10
 while True:
  if gateway.poll() is not None: raise RuntimeError("Gateway exited before readiness")
  try:
   with urlopen(transport.gateway_health_url,timeout=1) as r:
    health=json.load(r)
    if r.status==200 and health.get("instance_id"): break
  except Exception: pass
  if time.monotonic()>deadline: raise RuntimeError("Gateway health deadline")
  time.sleep(.5)
 state={"at_utc":datetime.now(timezone.utc).isoformat(),"ssh_pid":ssh.pid,
  "gateway_pid":gateway.pid,"instance_id":health["instance_id"],"gateway_bind":transport.gateway_bind,"upstream":transport.upstream,
  "source_revision":SOURCE_REVISION,
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
